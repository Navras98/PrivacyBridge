# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Test end-to-end dell'interfaccia PrivacyBridge via Playwright.

Requisiti (una tantum): ``pip install playwright && playwright install chromium``.

I test:
  1. Aprono l'app in Chromium headless collegandosi al FastAPI locale.
  2. Anonimizzano un testo italiano con più entità.
  3. Verificano che NESSUN valore reale compaia nel pannello destro
     (invariante di sicurezza primaria).
  4. Manipolano la tabella entità (rimuove / aggiunge / cambia tipo).
  5. Passano in modalità Ripristina e verificano che i valori tornino
     al posto giusto senza scambi.
  6. Sessioni: la nuova sessione parte vuota, la vecchia si ritrova.
  7. Carica un TXT + un PDF (piccoli, generati al volo).

Il vault usato è isolato in una temp dir (PRIVACYBRIDGE_DATA_DIR).
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

playwright_module = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fixture: server FastAPI in subprocess con vault isolato
# ---------------------------------------------------------------------------

def _porta() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    porta = _porta()
    data_dir = tmp_path_factory.mktemp("privacybridge_ui")
    env = os.environ.copy()
    env["PRIVACYBRIDGE_DATA_DIR"] = str(data_dir)
    env["PRIVACYBRIDGE_DB"] = str(data_dir / "vault.db")
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    # Il codice sta in src/, il cwd resta la radice: i percorsi relativi
    # del figlio continuano a puntare dove puntavano.
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "api.main:app",
            "--host", "127.0.0.1", "--port", str(porta),
            "--log-level", "critical",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{porta}"
    import urllib.request
    for _ in range(600):
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("server FastAPI non risponde")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def pagina(server, browser):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    ctx.set_default_timeout(15000)
    page = ctx.new_page()
    page.goto(server)
    page.wait_for_selector("#btn-anonimizza")
    yield page
    ctx.close()


# ---------------------------------------------------------------------------
# Testo di prova (10 valori reali distinti)
# ---------------------------------------------------------------------------

TESTO_PROVA = (
    "Gentile Mario Rossi, il colloquio è confermato in via Garibaldi 12, "
    "Milano. Contatti: mario.rossi@example.com, telefono 333 1234567. "
    "IBAN IT60X0542811101000000123456, codice fiscale RSSMRA80A01H501U. "
    "La conferma è stata data da Luigi Bianchi il 12 marzo 2026 per la "
    "società Beta Impianti in accordo con il fornitore."
)

VALORI_ATTESI = [
    "Mario Rossi",
    "mario.rossi@example.com",
    "333 1234567",
    "IT60X0542811101000000123456",
    "RSSMRA80A01H501U",
    "Luigi Bianchi",
    "12 marzo 2026",
    "Milano",
]


# ---------------------------------------------------------------------------
# 1. Struttura + presenza pannelli e tabella
# ---------------------------------------------------------------------------

def test_struttura_iniziale(pagina):
    # Nella vista Anonimizza (attiva di default) ci sono un pannello sx e uno dx.
    vista = pagina.locator("#vista-anonimizza")
    assert vista.locator(".pannello.sx").is_visible()
    assert vista.locator(".pannello.dx").is_visible()
    # Tabella entità (non la sezione suggerimenti, che è nascosta all'avvio).
    assert vista.locator(".tabella-box:not(.suggeriti)").is_visible()
    # La sezione "Possibili entità" esiste ma è nascosta finché non ci sono
    # suggerimenti da mostrare (FASE 5.4a).
    assert pagina.locator("#tabella-suggerimenti[hidden]").count() == 1
    # Tab attivo iniziale = Anonimizza
    assert pagina.locator('[data-tab="anonimizza"][aria-selected="true"]').count() == 1


# ---------------------------------------------------------------------------
# 2. Anonimizza + sicurezza (nessun valore reale nel pannello destro)
# ---------------------------------------------------------------------------

def test_anonimizza_e_nessun_leak(pagina):
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    anon = pagina.locator("#vista-anonimizzato").inner_text()

    # Nessuno dei valori reali chiave deve comparire.
    for v in ["Mario Rossi", "mario.rossi@example.com",
              "IT60X0542811101000000123456", "RSSMRA80A01H501U",
              "Luigi Bianchi"]:
        assert v not in anon, f"leak: {v!r} ancora presente in\n{anon}"

    # Deve contenere almeno un segnaposto.
    assert pagina.locator("#vista-anonimizzato .segnaposto").count() > 0


def test_pannello_sx_invariato_dopo_anonimizza(pagina):
    """FASE 1.1 — invariante di sicurezza primaria.

    Il pannello sinistro dopo 'Anonimizza' DEVE contenere ancora
    esattamente il testo originale, non quello anonimizzato. È così che
    l'utente può confrontare riga per riga e accorgersi di cosa è
    sfuggito.
    """
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    # `#vista-originale` è la vista di sola lettura del pannello sinistro
    # dopo Anonimizza (la textarea `#ta-originale` viene nascosta).
    sinistra = pagina.locator("#vista-anonimizza .pannello.sx #vista-originale")
    assert sinistra.is_visible(), (
        "dopo Anonimizza il pannello sinistro deve mostrare vista-originale"
    )

    testo_sx = sinistra.inner_text()

    # Il testo visibile del pannello sinistro DEVE essere il testo
    # originale non modificato (a meno di normalizzazioni degli
    # whitespace fatte da inner_text; il contenuto sostanziale coincide).
    assert testo_sx.strip() == TESTO_PROVA.strip(), (
        f"pannello sinistro modificato dopo Anonimizza.\n"
        f"atteso: {TESTO_PROVA!r}\n"
        f"trovato: {testo_sx!r}"
    )

    # Ogni singolo valore reale deve essere ancora presente a sinistra.
    for v in ["Mario Rossi", "mario.rossi@example.com",
              "IT60X0542811101000000123456", "RSSMRA80A01H501U",
              "Luigi Bianchi", "12 marzo 2026"]:
        assert v in testo_sx, (
            f"valore reale {v!r} sparito dal pannello sinistro: "
            "il testo originale deve restare visibile per il confronto."
        )

    # Nessun segnaposto («TIPO_N») deve comparire a sinistra: quelli
    # stanno solo a destra.
    import re as _re
    assert not _re.search(r"«[A-Z][A-Z_]*_\d+»", testo_sx), (
        f"segnaposti presenti nel pannello sinistro: {testo_sx!r}"
    )


# ---------------------------------------------------------------------------
# 3. Tabella entità: rimozione → il valore reale torna nel testo destro
# ---------------------------------------------------------------------------

def test_rimuove_entita(pagina):
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    # Rimuovo la prima riga.
    prima_val = pagina.locator("tbody .in-valore").first.input_value()
    pagina.locator("tbody .b-rimuovi").first.click()
    pagina.click("#btn-rianonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert prima_val in anon, (
        f"rimossa dalla tabella, il valore {prima_val!r} deve tornare nel testo:\n{anon}"
    )


# ---------------------------------------------------------------------------
# 4. Aggiunta entità a mano → sparisce dal testo
# ---------------------------------------------------------------------------

def test_aggiunge_entita_a_mano(pagina):
    testo = "L'incaricato è Federico Neri, contattabile all'ufficio."
    pagina.fill("#ta-originale", testo)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    pagina.click("#btn-aggiungi")
    input_nuovo = pagina.locator("tbody .in-valore").last
    input_nuovo.fill("ufficio")
    pagina.click("#btn-rianonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)
    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert "ufficio" not in anon


# ---------------------------------------------------------------------------
# 5. Cambio tipo → il segnaposto si aggiorna dopo rianonimizza
# ---------------------------------------------------------------------------

def test_cambia_tipo(pagina):
    # Serve un testo che produca almeno un'entità. "Beta Impianti" non
    # va più bene: il motore lo classifica (correttamente) come
    # organizzazione, e la categoria ORG è disattiva di default.
    pagina.fill("#ta-originale", "Il signor Mario Rossi ha inviato la conferma.")
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    # Cambia il primo tipo in "ALTRO"
    tipo = pagina.locator("tbody .sel-tipo").first
    tipo.select_option("ALTRO")
    pagina.click("#btn-rianonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)
    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert "«ALTRO_" in anon


# ---------------------------------------------------------------------------
# 6. Ripristina: tutti i valori tornano al posto giusto
# ---------------------------------------------------------------------------

def test_ripristina_roundtrip(pagina):
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    # Prendo il testo anonimizzato e i valori attesi.
    anon = pagina.locator("#vista-anonimizzato").inner_text()
    mappa = {}
    # Solo il tbody delle entità reali, non quello dei suggerimenti (FASE 5.4a).
    for row in pagina.locator("#tbody tr").all():
        ph = row.locator(".segnaposto").inner_text() if row.locator(".segnaposto").count() else ""
        val = row.locator(".in-valore").input_value()
        if ph and val:
            mappa[ph] = val

    # Passa a Ripristina.
    pagina.click('[data-tab="ripristina"]')
    pagina.fill("#ta-risposta", "Ecco la risposta: " + anon + " Grazie.")
    pagina.click("#btn-ripristina")
    pagina.wait_for_selector("#vista-ripristinato:not([hidden])", timeout=60_000)
    restored = pagina.locator("#vista-ripristinato").inner_text()

    for ph, val in mappa.items():
        assert val in restored, f"placeholder {ph!r} non ha restituito {val!r}"
        assert ph not in restored, f"segnaposto {ph!r} ancora presente in output"


# ---------------------------------------------------------------------------
# 7. Nuova sessione = vault isolato
# ---------------------------------------------------------------------------

def _apri_menu(pagina):
    """Dopo il redesign 2026-07-31, sessione/categorie/rubrica/vault/
    lingua/info sono raccolti nel menu 'Altro' — aperto da #btn-menu."""
    if pagina.locator("#menu").is_hidden():
        pagina.click("#btn-menu")
        pagina.wait_for_selector("#menu:not([hidden])", timeout=3000)


def test_sessioni_isolate(pagina):
    pagina.fill("#ta-originale", "Mario Rossi è arrivato oggi in ufficio.")
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)
    _apri_menu(pagina)
    prima_sessione = pagina.locator("#sel-sessione").input_value()

    pagina.click("#btn-nuova")
    pagina.wait_for_function(
        "arg => document.getElementById('sel-sessione').value !== arg", arg=prima_sessione
    )
    # La tabella deve essere vuota nella nuova sessione.
    assert pagina.locator("#tabella-vuota:not([hidden])").count() == 1


# ---------------------------------------------------------------------------
# 8. Carica un TXT
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# BUG 2 — Coerenza pannelli/tabella al cambio sessione
# ---------------------------------------------------------------------------

def test_bug2_cambio_sessione_azzera_tabella(pagina):
    """Dopo aver anonimizzato in una sessione, cambiando sessione la
    tabella deve svuotarsi in coerenza coi pannelli vuoti."""
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    # Tabella con almeno una riga.
    assert pagina.locator("#tbody tr").count() > 0

    # Cambio sessione (dal menu "Altro").
    _apri_menu(pagina)
    pagina.click("#btn-nuova")
    pagina.wait_for_selector("#tabella-vuota:not([hidden])", timeout=5000)

    # I pannelli devono essere vuoti E la tabella pure.
    assert pagina.locator("#tbody tr").count() == 0
    # ta-originale visibile e vuota (siamo tornati in modalità Modifica).
    assert pagina.locator("#ta-originale").is_visible()
    assert pagina.locator("#ta-originale").input_value() == ""
    # vista-anonimizzato vuota o nascosta.
    dx_vuoto = pagina.locator("#vuoto-dx")
    assert dx_vuoto.is_visible(), (
        "il placeholder 'incolla o carica' deve essere visibile a destra"
    )


# ---------------------------------------------------------------------------
# BUG 3 — Stato vuoto non deve stare SOPRA il contenuto
# ---------------------------------------------------------------------------

def test_bug3_stato_vuoto_nascosto_dopo_ripristina(pagina):
    """Nel pannello Ripristinato, dopo Ripristina, il testo del
    placeholder ('Incolla una risposta…') NON deve essere visibile
    insieme al testo ripristinato."""
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)
    anon = pagina.locator("#vista-anonimizzato").inner_text()

    pagina.click('[data-tab="ripristina"]')
    pagina.fill("#ta-risposta", anon)
    pagina.click("#btn-ripristina")
    pagina.wait_for_selector("#vista-ripristinato:not([hidden])", timeout=60_000)

    # Il div stato-vuoto NON deve essere visibile una volta che c'è
    # contenuto: se lo fosse, apparirebbe fluttuante sopra il testo.
    vuoto_rip = pagina.locator("#vuoto-rip")
    assert not vuoto_rip.is_visible(), (
        "lo stato vuoto 'Incolla una risposta…' deve sparire quando "
        "c'è testo ripristinato — altrimenti stanno sovrapposti."
    )


def test_bug3_stato_vuoto_nascosto_dopo_anonimizza(pagina):
    """Analogo per il pannello destro della vista Anonimizza."""
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)
    vuoto = pagina.locator("#vuoto-dx")
    assert not vuoto.is_visible(), (
        "lo stato vuoto del pannello anonimizzato deve sparire dopo Anonimizza."
    )


# ---------------------------------------------------------------------------
# BUG 1 end-to-end — Ripristino di segnaposto riformattati dall'LLM
# ---------------------------------------------------------------------------

def test_bug1_ripristina_placeholder_riformattati(pagina):
    """Simula la risposta di un LLM che ha ri-decorato i segnaposto:
    virgolette dritte, curve, backtick, markdown bold, nudo. Il
    ripristino deve funzionare in tutti i casi."""
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    # Prendi la mappa ph → valore reale dalla tabella.
    mappa = {}
    for row in pagina.locator("#tbody tr").all():
        if row.locator(".segnaposto").count():
            ph = row.locator(".segnaposto").inner_text()
            val = row.locator(".in-valore").input_value()
            if ph and val:
                mappa[ph[1:-1]] = val  # strip caporali «...»

    assert len(mappa) >= 3, f"servono almeno 3 entità, trovate {len(mappa)}"

    # Costruisci una risposta "come la darebbe un LLM": stripping dei
    # caporali, decorazioni varie.
    bodies = list(mappa.keys())
    parti = [
        f"Ho letto la richiesta di \"{bodies[0]}\".",
        f"Il documento cita anche `{bodies[1]}`.",
    ]
    if len(bodies) >= 3:
        parti.append(f"Infine si menziona **{bodies[2]}**.")
    for b in bodies[3:]:
        # nudo, senza decorazione
        parti.append(f"Riferimento: {b}.")
    risposta = " ".join(parti)

    pagina.click('[data-tab="ripristina"]')
    pagina.fill("#ta-risposta", risposta)
    pagina.click("#btn-ripristina")
    pagina.wait_for_selector("#vista-ripristinato:not([hidden])", timeout=60_000)
    restored = pagina.locator("#vista-ripristinato").inner_text()

    for body, val in mappa.items():
        assert val in restored, (
            f"placeholder {body!r} non ripristinato (val={val!r}) in\n{restored}"
        )
        # Il body originale non deve restare a video.
        assert body not in restored, (
            f"segnaposto {body!r} ancora presente in\n{restored}"
        )


def test_carica_txt(pagina, tmp_path):
    fpath = tmp_path / "prova.txt"
    fpath.write_text("Contatto: Anna Verdi, email anna@example.com.", encoding="utf-8")
    pagina.set_input_files("#file", str(fpath))
    # L'upload è asincrono (e con l'OCR può includere un polling di
    # avanzamento): attendi che il VALORE arrivi, non solo il selettore.
    pagina.wait_for_function(
        "document.getElementById('ta-originale').value.includes('Anna Verdi')",
        timeout=15_000,
    )
    assert "Anna Verdi" in pagina.locator("#ta-originale").input_value()


# ---------------------------------------------------------------------------
# FASE 5.4a — sezione "Possibili entità" separata dalla tabella entità
# ---------------------------------------------------------------------------

# Un cognome plausibile senza contesto personale: il motore lo propone
# invece di sostituirlo. Prima qui c'era "il gatto dorme vicino al
# camino" — funzionava perché "gatto" e "camino" stanno nella lista
# cognomi, ma erano esattamente i falsi suggerimenti che riempivano il
# riquadro sui documenti veri (84 su cinque file, di cui 4 persone).
# Ora il livello 3 scarta le parole del vocabolario italiano, e quel
# testo non suggerisce più niente — giustamente. "Bertini" non è una
# parola italiana, quindi l'indizio è vero e il suggerimento è quello
# che l'utente vedrà davvero.
TESTO_SUGGERIMENTO = "Il documento e stato firmato da Bertini in data odierna."


def test_fase5a_suggerimenti_in_sezione_dedicata(pagina):
    """Un testo che genera un suggerimento (cognome plausibile senza
    contesto personale) deve popolare la sezione "Possibili entità" e
    NON la tabella entità principale. Prima del fix, il suggerimento
    entrava nella tabella indistinguibile da una riga aggiunta a mano."""
    pagina.fill("#ta-originale", TESTO_SUGGERIMENTO)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    # La tabella entità principale deve essere vuota (nessuna sostituzione fatta).
    assert pagina.locator("#tabella-vuota:not([hidden])").count() == 1
    assert pagina.locator("#tbody tr").count() == 0

    # La sezione suggerimenti deve essere visibile con almeno una riga.
    box = pagina.locator("#tabella-suggerimenti")
    box.wait_for(state="visible")
    righe = pagina.locator("#tbody-suggerimenti tr")
    assert righe.count() >= 1, "atteso almeno un suggerimento per 'Bertini'"

    # Nessuna sostituzione fatta nel pannello destro.
    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert "Bertini" in anon, "il testo del pannello destro deve essere invariato"


def test_fase5a_promuovere_suggerimento_alla_tabella(pagina):
    """Spuntando la casella di un suggerimento, la voce si sposta nella
    tabella entità principale e sparisce dai suggerimenti."""
    pagina.fill("#ta-originale", TESTO_SUGGERIMENTO)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    # Spunta il primo suggerimento. Uso click (non check), perché il
    # nostro handler ridisegna la riga rimuovendo il checkbox dal DOM
    # subito dopo il click — check() invece attende una post-verifica
    # dello stato checked che sarebbe sempre in ritardo.
    pagina.locator("#tbody-suggerimenti .chk-trattieni").first.click()
    pagina.wait_for_selector("#tabella-suggerimenti", state="hidden", timeout=5000)

    # Ora la tabella entità ha una riga, i suggerimenti no.
    assert pagina.locator("#tbody tr").count() == 1
    # Se non ci sono più suggerimenti, la sezione è nascosta.
    assert pagina.locator("#tabella-suggerimenti[hidden]").count() == 1


# ---------------------------------------------------------------------------
# GATE 2 — sei casi limite funzionali (2026-07-30)
# ---------------------------------------------------------------------------

def test_gate2_ripristino_senza_segnaposto(pagina):
    """Ripristinare un testo che non contiene segnaposto → messaggio,
    non silenzio. La UI mostra il testo restituito uguale all'input e
    non solleva errori."""
    # Serve una sessione: la creo con un anonimizza minimale.
    pagina.fill("#ta-originale", "Nessuna entità in questo testo.")
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    pagina.click('[data-tab="ripristina"]')
    pagina.fill("#ta-risposta", "Un testo qualunque senza alcun segnaposto.")
    pagina.click("#btn-ripristina")
    pagina.wait_for_selector("#vista-ripristinato:not([hidden])", timeout=30_000)
    # Il testo torna uguale, e il conteggio dice 0 valori restituiti.
    metriche = pagina.locator("#metriche-rip-dx").inner_text()
    assert "0 valori restituiti" in metriche, metriche


def test_gate2_ripristino_segnaposto_altra_sessione(pagina):
    """Ripristinare un testo con segnaposto ignoti alla sessione attiva
    deve dare avviso esplicito, non silenzio."""
    pagina.fill("#ta-originale", "Nessuna entità qui.")
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    pagina.click('[data-tab="ripristina"]')
    pagina.fill("#ta-risposta", "Ecco «PERSONA_9999» e «EMAIL_9999».")
    pagina.click("#btn-ripristina")
    pagina.wait_for_selector("#vista-ripristinato:not([hidden])", timeout=30_000)
    # L'avviso deve comparire.
    assert pagina.locator("#avviso-rip:not([hidden])").count() == 1
    corpo = pagina.locator("#avviso-corpo").inner_text()
    assert "PERSONA_9999" in corpo


def test_gate2_elimina_ultima_sessione(pagina):
    """Eliminando l'ultima sessione rimasta, l'app resta usabile: una
    nuova sessione viene creata automaticamente e l'UI funziona."""
    # Assicuriamoci di avere una sessione con almeno un'entità.
    pagina.fill("#ta-originale", "Mario Rossi ha firmato.")
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)
    _apri_menu(pagina)
    sessione_iniziale = pagina.locator("#sel-sessione").input_value()

    # Elimina intercettando il confirm.
    pagina.once("dialog", lambda d: d.accept())
    pagina.click("#btn-elimina")
    # Dopo l'eliminazione, il selettore mostra una nuova sessione.
    pagina.wait_for_function(
        "arg => document.getElementById('sel-sessione').value !== arg",
        arg=sessione_iniziale,
    )
    # Pannelli vuoti, tabella vuota, ma la UI risponde.
    assert pagina.locator("#ta-originale").is_visible()
    assert pagina.locator("#tabella-vuota:not([hidden])").count() == 1
    # E posso anonimizzare di nuovo.
    pagina.fill("#ta-originale", "Anna Verdi conferma.")
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)


def test_gate2_doppio_click_anonimizza(pagina):
    """Doppio click ripetuto su Anonimizza non deve provocare doppie
    esecuzioni: il bottone si disabilita durante la chiamata."""
    pagina.fill("#ta-originale", "Mario Rossi ha firmato.")
    # dblclick emette 2 eventi click ravvicinati.
    pagina.locator("#btn-anonimizza").dblclick()
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)
    # Se ci fosse stata doppia esecuzione, avremmo entità duplicate o
    # sessioni doppie. Verifico che le entità siano coerenti.
    n_persone = pagina.locator('#tbody tr').count()
    assert n_persone >= 1
    # Nessuna sessione extra creata dal doppio click (dal menu Altro).
    _apri_menu(pagina)
    n_sessioni = pagina.locator("#sel-sessione option").count()
    # Dopo il primo anonimizza, esiste esattamente 1 sessione (o 0 se
    # l'implementazione lo salva dopo). Fondamentale: non ne compare più
    # di 1 come effetto del secondo click.
    assert n_sessioni <= 2


def test_gate2_resize_minimo(pagina):
    """Ridimensionando la viewport al minimo dichiarato (1000×700),
    nessun elemento chiave viene tagliato/nascosto e non c'è scroll
    orizzontale sul body. Dopo il redesign, la barra contiene solo
    marchio + tab + un pulsante menu; le voci secondarie vivono dentro
    il menu e devono essere visibili una volta aperto."""
    pagina.set_viewport_size({"width": 1000, "height": 700})
    # In barra: solo marchio, schede e menu unico.
    assert pagina.locator("#btn-menu").is_visible()
    assert pagina.locator('.scheda[data-tab="anonimizza"]').is_visible()
    assert pagina.locator('.scheda[data-tab="ripristina"]').is_visible()
    # Apro il menu: le voci raccolte devono essere raggiungibili.
    _apri_menu(pagina)
    for id_ in ["btn-nuova", "btn-elimina", "btn-categorie",
                "btn-rubrica", "btn-vault", "btn-info", "sel-sessione",
                "sel-lingua"]:
        el = pagina.locator(f"#{id_}")
        assert el.is_visible(), f"#{id_} non visibile a 1000x700 dentro il menu"
    # Chiudo il menu prima dei check di layout.
    pagina.keyboard.press("Escape")
    # I due pannelli e la tabella entità restano visibili.
    vista = pagina.locator("#vista-anonimizza")
    assert vista.locator(".pannello.sx").is_visible()
    assert vista.locator(".pannello.dx").is_visible()
    assert vista.locator(".tabella-box:not(.suggeriti)").is_visible()
    # No scroll orizzontale sul body.
    scroll_x = pagina.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert scroll_x <= 2, f"scroll orizzontale inatteso: {scroll_x}px"


def test_gate2_ui_regge_100k_caratteri(pagina):
    """100.000 caratteri incollati nella textarea: la UI resta
    reattiva. Verifico che il DOM accetti l'input e aggiorni il
    contatore caratteri istantaneamente (invariante UI, non backend).

    Non invoco anonimizza perché l'inferenza neurale su 100k richiede
    ~90s sulla macchina di dev (documentato in memory di progetto e in
    UI_AUDIT.md § Gate 2). Il fatto che l'UI accetti input grande
    senza freeze è ciò che l'utente sperimenta come "reattività":
    l'attesa dell'analisi è documentata dal messaggio di stato."""
    testo = "Il cliente Mario Rossi ha firmato. " * 3000
    assert len(testo) >= 100_000

    pagina.evaluate(
        "arg => { document.getElementById('ta-originale').value = arg; "
        "document.getElementById('ta-originale').dispatchEvent(new Event('input')); }",
        arg=testo,
    )
    # Il contatore caratteri è aggiornato subito.
    metriche = pagina.locator("#metriche-sx").inner_text()
    assert "caratteri" in metriche
    # Contiene "100" (le prime cifre di "100.000 caratteri" formattato
    # in italiano) o comunque un numero non banale.
    assert any(c.isdigit() for c in metriche)
    # Il DOM è ancora responsivo: posso cliccare un altro pulsante
    # istantaneamente (es. Svuota, contestuale — appare solo con testo).
    pagina.wait_for_selector("#btn-svuota:not([hidden])", timeout=3000)
    pagina.click("#btn-svuota")
    valore_dopo = pagina.locator("#ta-originale").input_value()
    assert valore_dopo == "", "la UI resta reattiva anche dopo input 100k"


def test_fase5bis_verifica_pre_copia(pagina):
    """Prima di copiare il testo anonimizzato, la UI fa un ultimo scan
    per pattern residui (email, IBAN, CF, ecc.). Se ne trova, chiede
    conferma tramite dialog."""
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    # Introduco artificialmente un residuo nel testo che sta per uscire.
    # Sfrutto la piccola API di test esposta in window.__pb (vedi
    # index.html — non usata dalla UI in produzione).
    pagina.evaluate(
        "window.__pb.stato.anonimizzato = window.__pb.stato.anonimizzato + "
        "' Nota: residuo@example.com resta.'"
    )

    dialoghi_visti = []
    pagina.on("dialog", lambda d: (dialoghi_visti.append(d.message), d.dismiss()))
    pagina.click("#btn-copia")
    # Il dialog è modale (confirm sincrono): dopo il click c'è già stato.
    pagina.wait_for_timeout(200)
    assert dialoghi_visti, "atteso un dialog di conferma per il residuo email"
    assert "residuo@example.com" in dialoghi_visti[0], (
        f"il dialog deve elencare il residuo trovato — messaggio: {dialoghi_visti[0]!r}"
    )


def test_fase5bis_copia_senza_residui_senza_dialog(pagina):
    """Se il testo anonimizzato non ha pattern residui, la copia parte
    senza dialog di conferma."""
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    dialoghi_visti = []
    pagina.on("dialog", lambda d: (dialoghi_visti.append(d.message), d.accept()))
    pagina.click("#btn-copia")
    pagina.wait_for_timeout(200)
    assert not dialoghi_visti, (
        f"non doveva apparire alcun dialog, invece è comparso: {dialoghi_visti}"
    )


def test_fase5c_preset_categorie(pagina):
    """I preset applicano un set predefinito di categorie con un click.
    Cambiando manualmente le checkbox, l'indicatore torna a Personalizzato."""
    _apri_menu(pagina)
    pagina.click("#btn-categorie")
    pagina.wait_for_selector("#velo-categorie:not([hidden])")
    # caricaCategorie è async: aspetta che i preset siano disegnati.
    pagina.wait_for_selector('#cat-preset .preset[data-preset="tecnico"]', timeout=10_000)

    # I 3 preset devono essere presenti.
    preset = pagina.locator("#cat-preset .preset[data-preset]")
    assert preset.count() == 3

    # Applico "Contratto" e verifico che diventi attivo + che ORG sia spuntato.
    pagina.click('[data-preset="contratto"]')
    pagina.wait_for_selector('[data-preset="contratto"].attivo', timeout=3000)
    # ORG (categoria non attiva per default) ora è spuntato.
    org_chk = pagina.locator('#cat-lista input[data-cat="ORG"]')
    assert org_chk.is_checked(), "ORG deve essere attivo col preset Contratto"

    # Applico "Documento tecnico" (default). ORG torna spento.
    pagina.click('[data-preset="tecnico"]')
    pagina.wait_for_selector('[data-preset="tecnico"].attivo', timeout=3000)
    assert not org_chk.is_checked(), "ORG deve essere spento col preset tecnico"


def test_fase5b_vault_vista_consultativa(pagina):
    """Dopo aver anonimizzato, il pulsante Vault mostra un elenco
    read-only dei segnaposto + tipo, coi valori reali nascosti finché
    non si preme Mostra valori."""
    pagina.fill("#ta-originale", TESTO_PROVA)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    _apri_menu(pagina)
    pagina.click("#btn-vault")
    pagina.wait_for_selector("#velo-vault:not([hidden])", timeout=5000)
    # caricaVault è async: aspetta che la tabella si sia popolata.
    pagina.wait_for_selector("#vault-elenco tbody tr", timeout=10_000)

    # Almeno un placeholder in tabella vault.
    assert pagina.locator("#vault-elenco tbody tr").count() >= 1
    # Valori nascosti (mostra i pallini).
    testo_vault = pagina.locator("#vault-elenco").inner_text()
    assert "Mario Rossi" not in testo_vault, "il valore reale non deve essere visibile finché non si clicca Mostra"
    assert "••••••" in testo_vault

    # Clicco Mostra valori.
    pagina.click("#btn-vault-mostra")
    testo_vault2 = pagina.locator("#vault-elenco").inner_text()
    assert "Mario Rossi" in testo_vault2, "dopo Mostra i valori reali devono comparire"

    # Chiudo con ESC.
    pagina.keyboard.press("Escape")
    pagina.wait_for_selector("#velo-vault", state="hidden", timeout=3000)


def test_fase5a_ignorare_suggerimento(pagina):
    """Cliccando la × su un suggerimento, la voce sparisce senza
    diventare un'entità."""
    pagina.fill("#ta-originale", TESTO_SUGGERIMENTO)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)

    n_prima = pagina.locator("#tbody-suggerimenti tr").count()
    assert n_prima >= 1

    pagina.locator("#tbody-suggerimenti .b-ignora").first.click()

    # Il numero di suggerimenti è diminuito, la tabella entità resta vuota.
    n_dopo = pagina.locator("#tbody-suggerimenti tr").count()
    assert n_dopo == n_prima - 1
    assert pagina.locator("#tbody tr").count() == 0


def test_ogni_categoria_ha_etichetta_italiana(pagina):
    """Nessuna sigla del motore deve arrivare sotto gli occhi dell'utente.

    Il dialogo "Cosa anonimizzare" elenca tutte le categorie del motore:
    se una manca dalla mappa ETICHETTA_TIPO, la UI ripiega sul codice
    grezzo e l'utente legge "CRYPTO", "MAC", "PRATICA". Il confronto è
    fatto contro la lista vera del backend, non contro una copia."""
    from backend.motore import CATEGORIE_TUTTE

    senza_etichetta = pagina.evaluate(
        "codici => codici.filter(c => !(c in window.__pb.ETICHETTA_TIPO))",
        sorted(CATEGORIE_TUTTE),
    )
    assert senza_etichetta == [], (
        "categorie del motore senza etichetta italiana in ETICHETTA_TIPO: "
        f"{senza_etichetta}"
    )

    # L'etichetta non deve coincidere con il codice interno, salvo dove il
    # codice È il nome italiano corrente: "IBAN" è la dicitura stampata su
    # ogni estratto conto, "CAP" quella di ogni modulo postale. Scriverli
    # per esteso allontanerebbe l'utente invece di avvicinarlo.
    nomi_correnti = {"IBAN", "CAP"}
    uguali = set(pagina.evaluate(
        "codici => codici.filter(c => window.__pb.ETICHETTA_TIPO[c] === c)",
        sorted(CATEGORIE_TUTTE),
    ))
    assert uguali <= nomi_correnti, (
        f"etichette identiche al codice interno: {sorted(uguali - nomi_correnti)}"
    )


# ---------------------------------------------------------------------------
# Percorso di click — il numero va misurato, non stimato
# ---------------------------------------------------------------------------

PERCORSO_MAX = 4


def _contatore_click(pagina):
    """Conta i click *reali* sulla pagina; restituisce azzera() e leggi().

    Filtra su ``isTrusted``: i click sintetici che la pagina emette da sé
    (``$("file").click()``) non sono gesti dell'utente e non vanno contati.
    Il conteggio lo fa il browser sugli eventi veri, non il test contandoli
    a mano dal codice — che è il modo di non accorgersi di un click in più.

    L'ascoltatore si installa una volta sola: registrandone uno per ogni
    tratto, ogni click verrebbe contato una volta per ascoltatore vivo e
    le misure crescerebbero da sole a ogni tratto successivo.
    """
    pagina.evaluate(
        "() => { window.__click = 0;"
        " document.addEventListener('click',"
        "   (e) => { if (e.isTrusted) window.__click++; }, true); }"
    )
    return (lambda: pagina.evaluate("() => { window.__click = 0; }"),
            lambda: pagina.evaluate("() => window.__click"))


def test_percorso_click_resta_breve(pagina):
    """I tre compiti principali devono restare entro 4 click.

    Non sono tre test separati perché il vincolo è sul percorso completo:
    anonimizzare e poi copiare è un compito solo, e spezzarlo nasconderebbe
    un click aggiunto in mezzo."""
    # Senza handler Playwright rifiuta ogni confirm: la copia si fermerebbe
    # a metà e il percorso misurato non sarebbe quello dell'utente.
    pagina.on("dialog", lambda d: d.accept())
    azzera, leggi = _contatore_click(pagina)
    misure: dict[str, int] = {}

    # 1. Anonimizzare un testo incollato e copiarlo.
    azzera()
    pagina.fill("#ta-originale", TESTO_PROVA)  # incollare non è un click
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)
    pagina.click("#btn-copia")
    misure["anonimizza e copia"] = leggi()

    anonimizzato = pagina.locator("#vista-anonimizzato").inner_text()

    # 2. Correggere un'entità in tabella e rianonimizzare.
    azzera()
    pagina.locator("tbody .in-valore").first.fill("Carla Verdi")
    pagina.locator("tbody .in-valore").first.dispatch_event("change")
    pagina.click("#btn-rianonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)
    pagina.click("#btn-copia")
    misure["correggi e ricopia"] = leggi()

    # 3. Ripristinare una risposta ricevuta.
    azzera()
    pagina.click('[data-tab="ripristina"]')
    pagina.fill("#ta-risposta", anonimizzato)
    pagina.click("#btn-ripristina")
    pagina.wait_for_selector("#vista-ripristinato:not([hidden])", timeout=60_000)
    pagina.click("#btn-copia-rip")
    misure["ripristina e copia"] = leggi()

    print("\npercorso di click misurato:")
    for nome, n in misure.items():
        print(f"  {nome}: {n} click")

    troppo_lunghi = {k: v for k, v in misure.items() if v > PERCORSO_MAX}
    assert not troppo_lunghi, (
        f"percorsi oltre {PERCORSO_MAX} click: {troppo_lunghi}"
    )


# ---------------------------------------------------------------------------
# La finestra non si blocca — requisito di prodotto, non di stile
# ---------------------------------------------------------------------------

# Analisi a modello caldo: è il caso che l'utente incontra sempre, e qui
# non c'è nessuna ragione perché il server rallenti. Misurato 162 ms nel
# peggiore dei 362 campioni su un documento da 90.696 caratteri.
LATENZA_ANALISI_MAX_S = 1.0
# Carico del modello: succede una volta sola. torch e spaCy tengono il GIL
# dentro codice C che non possiamo spezzare, quindi qualche blocco c'è —
# misurati 1163 ms nel peggiore dei casi. La soglia lascia margine per una
# macchina carica ma resta lontanissima dai 40s del difetto che presidia.
LATENZA_CARICO_MAX_S = 3.0


def test_server_risponde_durante_anonimizzazione(server):
    """Mentre analizza un documento lungo, l'app deve restare viva.

    L'analisi è lavoro CPU sincrono che dura decine di secondi. Chiamata
    direttamente dentro un endpoint ``async`` occuperebbe l'event loop e
    il server non risponderebbe più a nulla: la finestra si blocca, il
    polling dell'avanzamento non riceve risposta e la barra che dovrebbe
    mostrare il progresso mente. Va eseguita in threadpool.

    Il test non guarda il codice, misura: manda un'anonimizzazione e nel
    frattempo interroga ``/health``. Due fasi separate, perché sono due
    fenomeni diversi e mescolarli nasconderebbe il secondo: il carico del
    modello (una volta sola, blocchi brevi da codice C) e l'analisi vera
    e propria (ogni volta, e qui il server non deve rallentare affatto).
    """
    import statistics
    import threading
    import urllib.request

    doc = ROOT / "benchmark" / "documenti_utente" / "Hetepi_Agent_AI.pdf"
    if not doc.exists():
        pytest.skip("documento reale assente")
    from backend.documenti import carica
    testo, _ = carica(str(doc))

    def _latenza_health() -> float:
        t0 = time.perf_counter()
        with urllib.request.urlopen(f"{server}/health", timeout=120) as r:
            r.read()
        return time.perf_counter() - t0

    def _misura(testo_da_inviare: str) -> tuple[float, list[float]]:
        """Anonimizza in un thread e campiona ``/health`` finché dura."""
        esito: dict = {}

        def _posta() -> None:
            import json
            corpo = json.dumps({
                "testo": testo_da_inviare,
                "sessione": f"resp-{uuid.uuid4().hex[:8]}",
            }).encode()
            req = urllib.request.Request(
                f"{server}/anonimizza", data=corpo,
                headers={"Content-Type": "application/json"},
            )
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=900) as r:
                r.read()
            esito["durata"] = time.perf_counter() - t0

        lavoro = threading.Thread(target=_posta)
        lavoro.start()
        latenze = []
        while lavoro.is_alive():
            latenze.append(_latenza_health())
            time.sleep(0.1)
        lavoro.join(timeout=900)
        return esito.get("durata", 0.0), latenze

    # Riferimento a riposo: separa un server bloccato da una macchina lenta.
    _latenza_health()
    riposo = max(_latenza_health() for _ in range(5))

    durata_carico, lat_carico = _misura("Mario Rossi vive a Roma.")
    durata_analisi, lat_analisi = _misura(testo)

    assert lat_carico and lat_analisi, "nessun campione: analisi troppo breve"
    peggiore_carico = max(lat_carico)
    peggiore_analisi = max(lat_analisi)

    def _riga(nome: str, durata: float, lat: list[float]) -> str:
        return (f"{nome:<34} {durata:>6.1f}s   mediana "
                f"{statistics.median(lat) * 1000:>5.0f} ms   peggiore "
                f"{max(lat) * 1000:>6.0f} ms   ({len(lat)} campioni)")

    print(f"\n/health a riposo: {riposo * 1000:.0f} ms")
    print(_riga("carico modello + frase breve", durata_carico, lat_carico))
    print(_riga("analisi 90k, modello caldo", durata_analisi, lat_analisi))

    assert peggiore_analisi < LATENZA_ANALISI_MAX_S, (
        f"il server si blocca durante l'analisi: /health ha impiegato "
        f"{peggiore_analisi:.1f}s contro {riposo * 1000:.0f} ms a riposo"
    )
    assert peggiore_carico < LATENZA_CARICO_MAX_S, (
        f"il carico del modello blocca il server per {peggiore_carico:.1f}s"
    )


# Sotto i 100 ms un'interazione è percepita come istantanea: la finestra
# risponde "mentre" si clicca, non "dopo". Oltre, si sente il ritardo.
RISPOSTA_CLICK_MAX_MS = 100.0

# Il cronometro sta DENTRO la pagina, fra l'evento click e la mutazione
# vera del DOM. Misurare da Python includerebbe due giri di CDP e il
# polling del driver: la prima stesura di questo test lo faceva e
# leggeva 31-108 ms sulla stessa identica interazione, cioè il rumore
# del driver, non la finestra. Peggio: aspettava una condizione che era
# già vera prima del click, quindi non osservava affatto il cambiamento.
_JS_CRONOMETRO = """
([selBottone, selBersaglio, attributo]) => {
  window.__misura = null;
  let t0 = null;
  document.querySelector(selBottone).addEventListener(
    "click", () => { t0 = performance.now(); },
    { capture: true, once: true },
  );
  const obs = new MutationObserver(() => {
    if (t0 !== null && window.__misura === null) {
      window.__misura = performance.now() - t0;
      obs.disconnect();
    }
  });
  obs.observe(document.querySelector(selBersaglio),
              { attributes: true, attributeFilter: [attributo] });
}
"""


def _misura_click(pagina, sel_bottone: str, sel_bersaglio: str,
                  attributo: str) -> float:
    """Millisecondi dal click alla mutazione di ``attributo`` sul bersaglio."""
    pagina.evaluate(_JS_CRONOMETRO, [sel_bottone, sel_bersaglio, attributo])
    pagina.click(sel_bottone)
    pagina.wait_for_function("() => window.__misura !== null")
    return pagina.evaluate("() => window.__misura")


def test_risposta_al_click(pagina):
    """Le interazioni immediate devono restare immediate.

    Non riguarda l'analisi, che dura quanto deve: riguarda tutto il
    resto — cambiare tema, cambiare scheda, aprire il menu. Sono le
    azioni che l'utente fa mentre aspetta, e se rallentano è il segno
    che qualcosa di pesante è finito sul percorso del click.

    Il numero misurato arriva fino alla mutazione del DOM; il disegno
    segue nel frame successivo (≤ 17 ms a 60 Hz), che resta dentro il
    budget. Quello che il test esclude è solo il costo del driver.
    """
    misure = {
        "cambio tema": _misura_click(pagina, "#btn-tema", "html", "data-theme"),
        "cambio scheda": _misura_click(
            pagina, '[data-tab="ripristina"]', "#vista-ripristina", "hidden"),
        "apertura menu": _misura_click(pagina, "#btn-menu", "#menu", "hidden"),
    }

    print("\nrisposta al click (dal click alla mutazione del DOM):")
    for nome, ms in misure.items():
        print(f"  {nome:<16} {ms:>6.1f} ms")

    lente = {k: round(v, 1) for k, v in misure.items()
             if v > RISPOSTA_CLICK_MAX_MS}
    assert not lente, (
        f"interazioni oltre {RISPOSTA_CLICK_MAX_MS:.0f} ms: {lente}"
    )


def test_analisi_lunga_mostra_avanzamento_ed_e_annullabile(server, browser):
    """Su un documento lungo: l'avanzamento è reale e l'analisi si ferma.

    Il motore analizza ~2.500 caratteri al secondo. Mezzo milione di
    caratteri sono più di tre minuti e metà di quel tempo è inferenza del
    modello: nessuna ottimizzazione li toglie. Un'attesa così va mostrata
    con numeri veri e va potuta interrompere, altrimenti l'utente non sa
    se il programma sta lavorando o è morto.

    Il testo è quello di un PDF reale dell'utente, non una stringa
    scritta qui: su testo inventato misurerei la mia fantasia.
    """
    doc = ROOT / "benchmark" / "documenti_utente" / "Hetepi_Agent_AI.pdf"
    if not doc.exists():
        pytest.skip("documento reale assente")
    from backend.documenti import carica
    testo, _ = carica(str(doc))

    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    ctx.set_default_timeout(120_000)
    page = ctx.new_page()
    try:
        page.goto(server)
        page.wait_for_selector("#btn-anonimizza")
        page.fill("#ta-originale", testo)
        page.click("#btn-anonimizza")

        # 1. L'avanzamento arriva, e i numeri sono quelli del documento.
        page.wait_for_function(
            "() => /di [\\d.,]+ caratteri/.test"
            "(document.getElementById('stato').textContent)",
            timeout=120_000,
        )
        misura = page.locator("#stato").inner_text()
        numeri = [int(n.replace(".", "").replace(",", ""))
                  for n in re.findall(r"[\d.,]+", misura)]
        assert len(numeri) == 2, f"avanzamento non leggibile: {misura!r}"
        fatti, totali = numeri
        assert totali == len(testo), (
            f"il totale mostrato ({totali}) non è la lunghezza del "
            f"documento ({len(testo)}): l'avanzamento non è reale"
        )
        assert 0 < fatti <= totali, f"caratteri analizzati assurdi: {misura!r}"

        # 2. Il pulsante Annulla c'è e ferma davvero l'analisi.
        page.wait_for_selector("#btn-annulla:not([hidden])", timeout=10_000)
        t0 = time.perf_counter()
        page.click("#btn-annulla")
        page.wait_for_function(
            "() => document.getElementById('stato')"
            ".textContent.startsWith('Analisi annullata')",
            timeout=60_000,
        )
        fermata = time.perf_counter() - t0
        print(f"\navanzamento mostrato: {misura}")
        print(f"tempo per fermarsi dopo Annulla: {fermata:.1f}s")

        # 3. Dopo l'annullamento la finestra è di nuovo utilizzabile e il
        #    testo originale non è stato toccato.
        assert page.locator("#btn-anonimizza").is_enabled()
        assert page.locator("#btn-annulla").is_hidden()
        assert page.input_value("#ta-originale") == testo
    finally:
        ctx.close()


def test_finestra_scalda_il_motore_da_sola(server, browser):
    """La pagina, finita di disegnarsi, chiede il precarico del motore.

    Senza questa chiamata il modello si carica al primo click e l'utente
    aspetta ~9s in più, con qualche blocco da codice C nel mezzo. Con
    essa il carico cade nei secondi in cui la finestra è aperta e nessuno
    ha ancora incollato niente. Il test guarda le richieste che partono
    dal browser: se qualcuno toglie la riga dal frontend, ``/precarica``
    resta un endpoint che nessuno chiama e questo test se ne accorge.
    """
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    chiamate: list[str] = []
    page.on("request", lambda r: chiamate.append(r.url))
    try:
        page.goto(server)
        page.wait_for_selector("#btn-anonimizza")
        page.wait_for_function(
            "() => performance.getEntriesByType('resource')"
            ".some((e) => e.name.endsWith('/precarica'))",
            timeout=15000,
        )
    finally:
        ctx.close()
    assert any(u.endswith("/precarica") for u in chiamate), (
        f"la pagina non ha chiesto il precarico. Richieste: {chiamate}"
    )


# ---------------------------------------------------------------------------
# 13. MODIFICA DIRETTA SUL TESTO (Gate 2)
#     Ogni interazione descritta nel briefing ha qui il suo test: il
#     comando che compare al passaggio del mouse, il ripristino, il cambio
#     di tipo, la memoria in rubrica, la selezione libera a sinistra —
#     anche parziale —, l'evidenziazione nei due versi, l'annullamento e
#     un documento con più di cento entità.
# ---------------------------------------------------------------------------

def _anonimizza(pagina, testo: str) -> None:
    pagina.fill("#ta-originale", testo)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=120_000)


def _apri_comando(pagina, selettore: str):
    """Passa il mouse su un segnaposto e aspetta il comando contestuale."""
    # Sposta il mouse via prima: se stava già sopra il selettore, un hover
    # ripetuto non emette un nuovo mouseover e il timer di apertura non
    # parte. Succede fra due chiamate consecutive nello stesso test.
    pagina.mouse.move(0, 0)
    # Aspetta che il segnaposto sia effettivamente attaccato al DOM: dopo
    # una modifica diretta l'albero viene ridisegnato, e in Playwright il
    # locator .first può essere valutato prima che il nuovo nodo esista.
    pagina.wait_for_selector(selettore, timeout=5000)
    pagina.locator(selettore).first.hover()
    pagina.wait_for_selector("#comando-entita:not([hidden])", timeout=5000)
    return pagina.locator("#comando-entita")


def _agisci(pagina, bottone: str) -> str:
    """Preme una voce del comando e aspetta che il testo cambi davvero.

    ``#pannello-dx.completo`` non basta: dopo una modifica diretta il
    pannello non diventa mai obsoleto — è il punto della funzione — quindi
    quella classe non si spegne e riaspettarla non aspetta niente.
    """
    prima = pagina.locator("#vista-anonimizzato").inner_text()
    pagina.click(bottone)
    pagina.wait_for_function(
        "(p) => document.getElementById('vista-anonimizzato').innerText !== p",
        arg=prima, timeout=30_000,
    )
    return prima


# Selezione via DOM: Playwright non ha un'API per selezionare un intervallo
# di caratteri dentro un nodo, e serve poter chiedere anche mezza parola.
_JS_SELEZIONA = """
(arg) => {
  const radice = document.getElementById("vista-originale");
  const w = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT);
  const r = document.createRange();
  let n, tot = 0, fattoA = false, fattoB = false;
  while ((n = w.nextNode())) {
    const len = n.nodeValue.length;
    if (!fattoA && arg.a <= tot + len) { r.setStart(n, arg.a - tot); fattoA = true; }
    if (!fattoB && arg.b <= tot + len) { r.setEnd(n, arg.b - tot); fattoB = true; }
    tot += len;
    if (fattoB) break;
  }
  if (!fattoA || !fattoB) return false;
  const s = window.getSelection();
  s.removeAllRanges();
  s.addRange(r);
  radice.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  return true;
}
"""


def _seleziona(pagina, testo: str, sotto: str, inizio: int = 0, lung: int | None = None):
    """Seleziona ``sotto[inizio:inizio+lung]`` dentro il pannello sinistro."""
    base = testo.index(sotto) + inizio
    fine = base + (lung if lung is not None else len(sotto) - inizio)
    ok = pagina.evaluate(_JS_SELEZIONA, {"a": base, "b": fine})
    assert ok, f"selezione non riuscita su offset {base}-{fine}"


def test_fase6_hover_segnaposto_apre_comando(pagina):
    """2.1 — il comando compare al passaggio del mouse e porta due sole
    voci: Cambia tipo e Modifica valore. Ripristinare vive nella tabella
    (colonna "Rimuovi"), Ricordare sempre nella scheda "Rubrica"."""
    _anonimizza(pagina, TESTO_PROVA)
    menu = _apri_comando(pagina, "#vista-anonimizzato .segnaposto")

    for voce, atteso in [
        ("#ce-cambia", "Cambia tipo"),
        ("#ce-modifica", "Modifica valore"),
    ]:
        assert menu.locator(voce).inner_text().strip() == atteso, (
            f"voce {voce} assente o diversa da {atteso!r}"
        )

    # Le voci che erano nel menu prima non devono esserci più: la nuova
    # regola è che due voci bastano — se ne trova una terza, qualcuno le
    # ha rimesse per abitudine.
    assert menu.locator("#ce-ripristina").count() == 0, (
        "'Ripristinare' non deve stare nel menu contestuale: si rimuove "
        "dalla tabella"
    )
    assert menu.locator("#ce-ricorda").count() == 0, (
        "'Ricordare sempre' non deve stare nel menu contestuale: sta "
        "nella scheda Rubrica"
    )

    # Mostra il valore reale: è l'unico modo per sapere su quale entità
    # si sta agendo senza doverla cercare in tabella.
    assert pagina.locator("#ce-valore").inner_text().strip(), (
        "il comando non dice a quale valore si riferisce"
    )

    # Resta aperto finché il mouse ci sta sopra.
    pagina.locator("#ce-modifica").hover()
    pagina.wait_for_timeout(500)
    assert pagina.locator("#comando-entita").is_visible(), (
        "il comando si è chiuso mentre il mouse era sopra di esso"
    )


def test_fase6_comando_non_e_immediato(pagina):
    """2.1 — 'compare con un ritardo di 200-300 ms': non deve lampeggiare
    addosso a chi sta solo attraversando il testo col mouse."""
    _anonimizza(pagina, TESTO_PROVA)
    pagina.locator("#vista-anonimizzato .segnaposto").first.hover()
    pagina.wait_for_timeout(120)
    assert pagina.locator("#comando-entita").is_hidden(), (
        "il comando è comparso prima di 120 ms: attraversare il testo col "
        "mouse lo farebbe sbattere in faccia all'utente"
    )
    pagina.wait_for_selector("#comando-entita:not([hidden])", timeout=5000)


def test_fase6_cambia_tipo_dal_testo(pagina):
    """2.1 — cambio di tipo direttamente dal testo."""
    _anonimizza(pagina, "Il signor Mario Rossi ha inviato la conferma.")
    _apri_comando(pagina, "#vista-anonimizzato .segnaposto")
    valore = pagina.locator("#ce-valore").inner_text().strip()

    pagina.click("#ce-cambia")
    pagina.wait_for_selector("#ce-riga-tipi:not([hidden])", timeout=3000)
    pagina.select_option("#ce-tipi", "ALTRO")
    _agisci(pagina, "#ce-conferma")

    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert "«ALTRO_" in anon, f"tipo non cambiato:\n{anon}"
    # E la tabella lo dice, senza premere nulla.
    for r in pagina.locator("#tbody tr").all():
        if r.locator(".in-valore").input_value() == valore:
            assert r.locator(".sel-tipo").input_value() == "ALTRO"
            break
    else:
        raise AssertionError(f"riga {valore!r} sparita dalla tabella")


def _modifica_valore(pagina, nuovo: str) -> None:
    """Apre il campo di modifica valore, digita ``nuovo``, conferma e
    aspetta che il testo anonimizzato cambi davvero."""
    pagina.click("#ce-modifica")
    pagina.wait_for_selector("#ce-riga-modifica:not([hidden])", timeout=3000)
    inp = pagina.locator("#ce-valore-input")
    inp.fill(nuovo)
    _agisci(pagina, "#ce-conferma-valore")


def _apri_comando_via_tastiera(pagina, selettore: str):
    """Come _apri_comando ma usa focus+Invio: più solido dell'hover fra
    due modifiche consecutive, perché non dipende dal riemettersi degli
    eventi mouseover dopo un ridisegno del DOM."""
    pagina.wait_for_selector(selettore, timeout=5000)
    pagina.locator(selettore).first.focus()
    pagina.keyboard.press("Enter")
    pagina.wait_for_selector("#comando-entita:not([hidden])", timeout=5000)
    return pagina.locator("#comando-entita")


def test_fase6_modifica_valore_accorcia_lo_span(pagina):
    """2.5 — modifica valore che accorcia lo span: la parte tagliata torna
    in chiaro nel testo anonimizzato, il ripristino resta byte-identico.

    Costruita per l'esempio del difetto reale: se il motore avesse preso
    "Il paziente Mario Rossi" come persona, correggerlo a "Mario Rossi"
    deve riportare "Il paziente " nel testo di destra e non rompere il
    roundtrip.
    """
    # Uso un nome diverso da quello del test cambia_tipo, che potrebbe
    # aver lasciato Mario Rossi memorizzato con tipo ALTRO nella sessione
    # riusata dal client (localStorage nuovo ma il server condivide le
    # sessioni: dettaglio di test-isolation che si può ignorare finché
    # non tocca la funzione in prova).
    testo = "Il paziente Giulia Verdi ha firmato oggi."
    _anonimizza(pagina, testo)
    _apri_comando_via_tastiera(pagina, "#vista-anonimizzato .segnaposto")
    valore_prima = pagina.locator("#ce-valore").inner_text().strip()
    assert "Giulia Verdi" in valore_prima
    # Simula un allungamento manuale: l'utente vuole coprire di più.
    _modifica_valore(pagina, "Il paziente Giulia Verdi")

    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert "Il paziente Giulia Verdi" not in anon, (
        f"il valore esteso avrebbe dovuto sparire dall'uscita:\n{anon}"
    )
    assert "«PERSONA_" in anon, f"tipo cambiato inaspettatamente: {anon!r}"
    # Ora accorcia di nuovo a "Giulia Verdi": "Il paziente " deve
    # ricomparire nell'uscita.
    _apri_comando_via_tastiera(pagina, "#vista-anonimizzato .segnaposto")
    _modifica_valore(pagina, "Giulia Verdi")
    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert "Il paziente" in anon, (
        f"'Il paziente' doveva tornare in chiaro dopo l'accorciamento:\n{anon}"
    )
    assert "«PERSONA_" in anon


def test_fase6_modifica_valore_allunga_lo_span(pagina):
    """2.5 — allungare il valore: la parte aggiunta sparisce dal testo
    anonimizzato e resta nel vault (roundtrip esatto)."""
    testo = "Ciao sono Matteo Rossi nato a Roma."
    _anonimizza(pagina, testo)
    _apri_comando(pagina, "#vista-anonimizzato .segnaposto")
    _modifica_valore(pagina, "Matteo Rossi nato a Roma")

    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert "Matteo" not in anon, (
        f"il valore esteso doveva sparire per intero:\n{anon}"
    )
    # E il ripristino deve tornare identico all'originale.
    pagina.click('[data-tab="ripristina"]')
    pagina.wait_for_selector("#vista-ripristina:not([hidden])")
    pagina.fill("#ta-risposta", anon)
    pagina.click("#btn-ripristina")
    pagina.wait_for_selector("#vista-ripristinato:not([hidden])", timeout=30_000)
    rip = pagina.locator("#vista-ripristinato").inner_text()
    assert rip == testo, (
        f"roundtrip non esatto dopo l'allungamento:\n  in : {testo!r}\n  rip: {rip!r}"
    )


def test_fase6_modifica_valore_sposta_lo_span(pagina):
    """2.5 — cambiare il valore su un altro tratto del testo: la vecchia
    posizione torna in chiaro, quella nuova viene coperta."""
    testo = "Mario Rossi lavora con Anna Verdi da lunedì."
    _anonimizza(pagina, testo)
    # Apri il comando sul primo segnaposto (Mario Rossi).
    _apri_comando_via_tastiera(pagina, "#vista-anonimizzato .segnaposto")
    valore_prima = pagina.locator("#ce-valore").inner_text().strip()
    assert valore_prima == "Mario Rossi"
    # Sposta il valore da "Mario Rossi" a "Anna Verdi": la vecchia
    # posizione deve tornare in chiaro e la nuova viene sostituita.
    _modifica_valore(pagina, "Anna Verdi")

    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert "Mario Rossi" in anon, (
        f"la vecchia posizione doveva tornare in chiaro:\n{anon}"
    )
    assert "Anna Verdi" not in anon, (
        f"la nuova posizione doveva essere coperta:\n{anon}"
    )


def test_fase6_modifica_valore_roundtrip_byte_identico(pagina):
    """2.5 — dopo qualsiasi modifica manuale, il ripristino torna
    identico byte per byte all'originale."""
    testo = "Il signor Mario Rossi ha firmato il documento."
    _anonimizza(pagina, testo)
    _apri_comando(pagina, "#vista-anonimizzato .segnaposto")
    _modifica_valore(pagina, "signor Mario Rossi")

    anon = pagina.locator("#vista-anonimizzato").inner_text()
    pagina.click('[data-tab="ripristina"]')
    pagina.wait_for_selector("#vista-ripristina:not([hidden])")
    pagina.fill("#ta-risposta", anon)
    pagina.click("#btn-ripristina")
    pagina.wait_for_selector("#vista-ripristinato:not([hidden])", timeout=30_000)
    rip = pagina.locator("#vista-ripristinato").inner_text()
    assert rip == testo, (
        f"roundtrip non esatto:\n  in : {testo!r}\n  rip: {rip!r}"
    )


def test_fase6_selezione_anonimizza_dal_pannello_sinistro(pagina):
    """2.2 — selezionare del testo a sinistra offre di anonimizzarlo."""
    testo = "Il documento è stato consegnato allo sportello Q dal fattorino."
    _anonimizza(pagina, testo)
    _seleziona(pagina, testo, "fattorino")

    pagina.wait_for_selector("#comando-selezione:not([hidden])", timeout=5000)
    assert pagina.locator("#cs-valore").inner_text().strip() == "fattorino"

    pagina.select_option("#cs-tipi", "ALTRO")
    _agisci(pagina, "#cs-anonimizza")

    anon = pagina.locator("#vista-anonimizzato").inner_text()
    assert "fattorino" not in anon, f"la selezione non è stata anonimizzata:\n{anon}"
    assert "«ALTRO_" in anon
    valori = [i.input_value() for i in pagina.locator("#tbody .in-valore").all()]
    assert "fattorino" in valori, "la nuova entità non compare in tabella"


def test_fase6_selezione_parziale_aggancia_alla_parola(pagina):
    """2.2 — 'deve funzionare anche su selezioni parziali: aggancia ai
    confini di parola'."""
    testo = "Il documento è stato consegnato allo sportello dal fattorino."
    _anonimizza(pagina, testo)
    # Solo "ttor", in mezzo a "fattorino".
    _seleziona(pagina, testo, "fattorino", inizio=3, lung=4)

    pagina.wait_for_selector("#comando-selezione:not([hidden])", timeout=5000)
    assert pagina.locator("#cs-valore").inner_text().strip() == "fattorino", (
        "mezza parola selezionata: il comando deve proporre la parola intera"
    )


def test_fase6_selezione_non_ingoia_la_punteggiatura(pagina):
    """2.2 — l'aggancio ai confini si ferma al punto di fine frase, ma
    tiene insieme i punti interni di un indirizzo email."""
    # Nessuna delle due parole messe alla prova è un'entità: se lo fosse
    # si aprirebbe l'altro comando e il test misurerebbe altro.
    testo = "Il pre-avviso per Mario Rossi è stato affisso allo sportello."
    _anonimizza(pagina, testo)

    _seleziona(pagina, testo, "sportello", inizio=2, lung=3)
    pagina.wait_for_selector("#comando-selezione:not([hidden])", timeout=5000)
    assert pagina.locator("#cs-valore").inner_text().strip() == "sportello", (
        "il punto che chiude la frase non fa parte della parola"
    )

    pagina.keyboard.press("Escape")
    _seleziona(pagina, testo, "pre-avviso", inizio=5, lung=3)
    pagina.wait_for_selector("#comando-selezione:not([hidden])", timeout=5000)
    assert pagina.locator("#cs-valore").inner_text().strip() == "pre-avviso", (
        "il trattino fra due lettere tiene insieme la parola"
    )


def test_fase6_selezione_propone_gia_il_tipo_probabile(pagina):
    """2.2 — 'scegliendo il tipo, col più probabile già proposto'.

    La categoria "indirizzo web" è spenta di default, quindi quel valore
    non è un'entità: il tipo che compare nella tendina può venire solo
    dalla forma della selezione.
    """
    testo = "La circolare è pubblicata su www.esempio.test da lunedì."
    _anonimizza(pagina, testo)
    _seleziona(pagina, testo, "www.esempio.test", inizio=6, lung=4)

    pagina.wait_for_selector("#comando-selezione:not([hidden])", timeout=5000)
    assert pagina.locator("#cs-valore").inner_text().strip() == "www.esempio.test"
    assert pagina.locator("#cs-tipi").input_value() == "URL", (
        "il tipo più probabile va proposto da solo, non cercato nella tendina"
    )
    assert "indirizzo web" in pagina.locator("#cs-anonimizza").inner_text().lower(), (
        "la voce del comando deve dire in italiano cosa sta per fare"
    )


def test_fase6_selezione_su_entita_esistente_propone_modifica(pagina):
    """2.2 — 'se è già coperto da un'entità, proponi di modificarla'."""
    testo = "Il signor Mario Rossi ha inviato la conferma."
    _anonimizza(pagina, testo)
    _seleziona(pagina, testo, "Mario Rossi", inizio=0, lung=5)

    pagina.wait_for_selector("#comando-entita:not([hidden])", timeout=5000)
    assert pagina.locator("#comando-selezione").is_hidden(), (
        "su un valore già anonimizzato non si offre di anonimizzarlo di nuovo"
    )
    assert "Mario Rossi" in pagina.locator("#ce-valore").inner_text()


def test_fase6_evidenziazione_nei_due_versi(pagina):
    """2.3 — l'evidenziazione è reciproca in entrambe le direzioni."""
    _anonimizza(pagina, TESTO_PROVA)

    # Da destra a sinistra.
    chip = pagina.locator("#vista-anonimizzato .segnaposto").first
    ph = chip.inner_text().strip()
    chip.hover()
    gemello_sx = pagina.locator(f'#vista-originale [data-ph="{ph}"]').first
    pagina.wait_for_function(
        "(p) => { const n = document.querySelector"
        "(`#vista-originale [data-ph=\"${p}\"]`); return n && n.classList.contains('acceso'); }",
        arg=ph, timeout=3000,
    )
    assert gemello_sx.evaluate("n => n.classList.contains('acceso')")
    # E la riga della tabella si accende insieme.
    assert pagina.locator(f'#tbody tr[data-ph="{ph}"]').first.evaluate(
        "n => n.classList.contains('acceso')"
    ), "la riga in tabella non si accende"

    # Da sinistra a destra.
    pagina.keyboard.press("Escape")
    pagina.locator("#metriche-sx").hover()
    gemello_sx.hover()
    pagina.wait_for_function(
        "(p) => { const n = document.querySelector"
        "(`#vista-anonimizzato [data-ph=\"${p}\"]`); return n && n.classList.contains('acceso'); }",
        arg=ph, timeout=3000,
    )


def test_fase6_annulla_con_scorciatoia(pagina):
    """2.4 — 'annullabile con Cmd+Z / Ctrl+Z'."""
    _anonimizza(pagina, TESTO_PROVA)
    anon_prima = pagina.locator("#vista-anonimizzato").inner_text()

    _apri_comando(pagina, "#vista-anonimizzato .segnaposto")
    pagina.click("#ce-cambia")
    pagina.wait_for_selector("#ce-riga-tipi:not([hidden])", timeout=3000)
    pagina.select_option("#ce-tipi", "ALTRO")
    _agisci(pagina, "#ce-conferma")
    assert "«ALTRO_" in pagina.locator("#vista-anonimizzato").inner_text()

    pagina.keyboard.press("Control+z")
    pagina.wait_for_function(
        "(t) => document.getElementById('vista-anonimizzato').innerText === t",
        arg=anon_prima, timeout=30_000,
    )
    assert pagina.locator("#vista-anonimizzato").inner_text() == anon_prima, (
        "annullando, il testo deve tornare identico a com'era — "
        "segnaposto compresi"
    )


def test_fase6_tastiera_raggiunge_le_entita(pagina):
    """2.4 — 'raggiungibile da tastiera: Tab naviga fra le entità, Invio
    apre'."""
    _anonimizza(pagina, TESTO_PROVA)
    chip = pagina.locator("#vista-anonimizzato .segnaposto").first
    assert chip.get_attribute("tabindex") == "0", (
        "i segnaposto nel testo devono stare nell'ordine di tabulazione"
    )
    chip.focus()
    pagina.keyboard.press("Enter")
    pagina.wait_for_selector("#comando-entita:not([hidden])", timeout=5000)

    # Escape chiude e riporta il fuoco dove stava.
    pagina.keyboard.press("Escape")
    pagina.wait_for_selector("#comando-entita", state="hidden", timeout=3000)
    assert chip.evaluate("n => n === document.activeElement"), (
        "chiudendo col tasto Esc il fuoco deve tornare al segnaposto"
    )


def test_fase6_comando_non_sposta_il_layout(pagina):
    """2.4 — 'nessuno spostamento di layout'."""
    _anonimizza(pagina, TESTO_PROVA)
    misure = ["#pannello-sx", "#pannello-dx", "#vista-anonimizzato", "#tbody"]
    prima = {s: pagina.locator(s).bounding_box() for s in misure}

    _apri_comando(pagina, "#vista-anonimizzato .segnaposto")
    dopo = {s: pagina.locator(s).bounding_box() for s in misure}

    for s in misure:
        assert prima[s] == dopo[s], (
            f"{s} si è spostato all'apertura del comando: {prima[s]} → {dopo[s]}"
        )


# Nomi italiani veri: il motore deve trovarli davvero, altrimenti il test
# misurerebbe un documento inventato invece del comportamento reale.
_NOMI_100 = [
    f"{n} {c}"
    for c in ["Rossi", "Bianchi", "Ferrari", "Esposito", "Romano",
              "Colombo", "Ricci", "Marino", "Greco", "Bruno"]
    for n in ["Marco", "Giulia", "Alessandro", "Francesca", "Lorenzo",
              "Chiara", "Matteo", "Silvia", "Davide", "Elena",
              "Riccardo", "Martina"]
]


def test_fase6_documento_con_oltre_cento_entita(pagina):
    """Gate 2 — 'un documento reale con 100+ entità'.

    Non basta che la finestra regga: la modifica diretta deve restare
    utilizzabile, e il passaggio del mouse non deve ricalcolare il testo.
    """
    righe = [f"Riga {i}: la pratica è assegnata a {n} della sede." 
             for i, n in enumerate(_NOMI_100)]
    testo = "\n".join(righe)
    t0 = time.perf_counter()
    _anonimizza(pagina, testo)
    print(f"\nanonimizzazione di {len(testo)} caratteri: {time.perf_counter() - t0:.1f}s")

    n_entita = pagina.locator("#tbody tr").count()
    print(f"entità in tabella: {n_entita}")
    assert n_entita >= 100, (
        f"il documento doveva produrre almeno 100 entità, ne ha prodotte {n_entita}"
    )

    # Passaggio del mouse su venti segnaposto diversi: nessun ridisegno
    # del testo, e il tempo deve restare quello di un cambio di classe.
    chips = pagina.locator("#vista-anonimizzato .segnaposto")
    ms = pagina.evaluate(
        """() => {
          const n = document.querySelectorAll('#vista-anonimizzato .segnaposto');
          const t0 = performance.now();
          for (let i = 0; i < 20 && i < n.length; i++) {
            n[i].dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
          }
          return performance.now() - t0;
        }"""
    )
    print(f"20 passaggi del mouse su {chips.count()} segnaposto: {ms:.0f} ms")
    assert ms < 400, (
        f"l'evidenziazione costa {ms:.0f} ms per venti passaggi: su un "
        "documento del genere il mouse diventa appiccicoso"
    )

    # E la modifica diretta funziona lo stesso, con tutte quelle entità.
    t0 = time.perf_counter()
    _apri_comando(pagina, "#vista-anonimizzato .segnaposto")
    valore = pagina.locator("#ce-valore").inner_text().strip()
    pagina.click("#ce-cambia")
    pagina.wait_for_selector("#ce-riga-tipi:not([hidden])", timeout=3000)
    pagina.select_option("#ce-tipi", "ALTRO")
    _agisci(pagina, "#ce-conferma")
    dt = time.perf_counter() - t0
    print(f"modifica diretta con {n_entita} entità: {dt:.2f}s")
    # La stessa entità è ancora in tabella ma con tipo nuovo.
    for r in pagina.locator("#tbody tr").all():
        if r.locator(".in-valore").input_value() == valore:
            assert r.locator(".sel-tipo").input_value() == "ALTRO"
            break
    else:
        raise AssertionError(
            f"riga {valore!r} sparita: la modifica di tipo non deve rimuoverla"
        )


# ==========================================================================
# 14. La firma del prodotto
# ==========================================================================


def test_firma_e_sempre_visibile(pagina):
    """3.1 — 'in basso a destra, sempre visibile e discreta'.

    'Sempre' vuol dire anche a schermo vuoto e nell'altra scheda: una
    firma che compare solo a lavoro fatto non è una firma, è un esito.
    """
    firma = pagina.locator("#firma-prodotto")
    assert firma.is_visible(), "la firma non c'è a schermo vuoto"
    assert firma.inner_text().strip() == "PrivacyBridge by @Andrea Sforna"

    pagina.click('[data-tab="ripristina"]')
    pagina.wait_for_selector("#vista-ripristina:not([hidden])")
    assert firma.is_visible(), "la firma sparisce nella scheda Ripristina"

    pagina.click("#btn-tema")
    pagina.wait_for_function(
        "() => document.documentElement.dataset.theme === 'scuro'")
    assert firma.is_visible(), "la firma sparisce nel tema scuro"


def test_firma_in_basso_a_destra(pagina):
    """Ultima riga a destra, a filo del bordo del pannello.

    Il riquadro del contenitore è largo quanto la finestra: quello che si
    vede è il testo, ed è il testo che va misurato.
    """
    vista = pagina.viewport_size
    inizio = pagina.locator("#firma-prodotto .firma-marchio").bounding_box()
    fine = pagina.locator("#firma-prodotto .firma-autore").bounding_box()
    pannello = pagina.locator("#pannello-dx").bounding_box()

    assert inizio["x"] > vista["width"] * 0.5, "la firma non è a destra"
    assert fine["y"] > vista["height"] * 0.9, "la firma non è in basso"
    assert vista["height"] - (fine["y"] + fine["height"]) <= 12, (
        "la firma non tocca il fondo: sembra appoggiata, non firmata")
    assert abs((fine["x"] + fine["width"]) - (pannello["x"] + pannello["width"])) <= 2, (
        "la firma non è allineata al bordo destro del pannello")


def test_firma_non_copre_il_contenuto_quando_si_scorre(pagina):
    """Il punto per cui non è ``position: fixed``.

    ``main`` scorre. Una firma fissa sopra la tela finisce a cavallo di
    una riga della tabella appena il documento supera la finestra, ed è
    lì che smette di essere una firma e diventa un'etichetta appiccicata.
    Nel flusso della colonna il caso non può presentarsi: si verifica
    proprio nella condizione che lo produrrebbe.
    """
    _anonimizza(pagina, "\n".join(
        f"Riga {i}: pratica di {n}." for i, n in enumerate(_NOMI_100[:40])))
    altezza = pagina.evaluate(
        "() => { const m = document.querySelector('main');"
        " m.scrollTop = m.scrollHeight; return m.scrollHeight - m.clientHeight; }")
    assert altezza > 0, "il caso non è stato riprodotto: main non scorre"

    r = pagina.locator("#firma-prodotto").bounding_box()
    for sel in (".fondo", "#pannello-sx", "#pannello-dx"):
        c = pagina.locator(sel).first.bounding_box()
        assert c["y"] + c["height"] <= r["y"] + 1, (
            f"{sel} finisce sotto la firma: si sovrappongono")


def test_firma_sotto_i_dialoghi(pagina):
    """Un velo modale la deve coprire, non il contrario."""
    r = pagina.locator("#firma-prodotto").bounding_box()
    pagina.click("#btn-menu")
    pagina.click("#btn-info")
    pagina.wait_for_selector("#velo-info:not([hidden])")
    sopra = pagina.evaluate(
        "([x, y]) => { const e = document.elementFromPoint(x, y);"
        " return e && e.closest('#velo-info') ? 'velo' : (e ? e.id || e.tagName : ''); }",
        [r["x"] + r["width"] / 2, r["y"] + r["height"] / 2],
    )
    assert sopra == "velo", (
        f"sul punto della firma, con il dialogo aperto, c'è {sopra!r}: "
        "la firma buca il velo modale")
