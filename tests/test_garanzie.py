# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Test delle sei garanzie di prodotto (FASE 5-bis).

Ogni garanzia è indipendente e testata separatamente. Il file può
essere eseguito da solo per stampare un riepilogo leggibile:

    python -m tests.test_garanzie

Le sei garanzie:
    G1 — Deterministico: stesso input → stesso output.
    G2 — Mai corrompe: nessuna sostituzione a metà parola, nessuna
         attraverso a-capo, nessuno scambio di segnaposto.
    G3 — Zero fughe strutturati: IBAN/CF/PIVA/EMAIL/TELEFONO/CARTA
         verificati aritmeticamente vengono sempre catturati.
    G4 — Ripristino esatto: deanonimizza(anonimizza(X)) == X.
    G5 — Segnaposto coerenti: stessa entità → stesso segnaposto.
    G6 — Mai silenzioso: ogni sostituzione appare nella lista entità.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

# Sotto pytest ci penserebbe `pythonpath` in pyproject.toml, ma questo
# file si esegue anche da solo (vedi __main__ in fondo): lanciato così,
# senza questa riga, l'import qui sotto non troverebbe backend.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from backend.motore import anonimizza, deanonimizza

PH_RE = re.compile(r"«[A-Za-z][A-Za-z_]*_\d+»")


@pytest.fixture
def vault_temp(tmp_path):
    """Vault isolato in tmp per ogni test."""
    return str(tmp_path / "garanzie.db")


# ---------------------------------------------------------------------------
# G1 — Deterministico
# ---------------------------------------------------------------------------

def test_g1_deterministico(vault_temp):
    testo = (
        "Gentile Mario Rossi, l'IBAN IT60X0542811101000000123456 è confermato. "
        "Contatti: mario.rossi@example.com, tel. +39 333 1234567. "
        "CF: RSSMRA80A01H501U."
    )
    a1, e1 = anonimizza(testo, "s1", db_path=vault_temp)
    a2, e2 = anonimizza(testo, "s1", db_path=vault_temp)
    assert a1 == a2, "output di anonimizza non deterministico"
    # Le entità sono identiche (stesso ordinamento, stesso contenuto).
    ent1_norm = sorted((e["tipo"], e["valore_reale"], e.get("placeholder", "")) for e in e1)
    ent2_norm = sorted((e["tipo"], e["valore_reale"], e.get("placeholder", "")) for e in e2)
    assert ent1_norm == ent2_norm, "entità differenti fra due esecuzioni identiche"


# ---------------------------------------------------------------------------
# G2 — Mai corrompe il testo
# ---------------------------------------------------------------------------

def test_g2_no_metà_parola(vault_temp):
    """Un segnaposto non deve mai apparire in mezzo a un token del testo."""
    testo = (
        "Il cliente Mario Rossi ha telefonato oggi. La marioverdi@example.com "
        "è di un altro Mario."
    )
    anon, _ = anonimizza(testo, "s2a", db_path=vault_temp)
    # Ogni segnaposto è separato da bordi non-parola su entrambi i lati.
    for m in PH_RE.finditer(anon):
        prima = anon[m.start() - 1] if m.start() > 0 else " "
        dopo = anon[m.end()] if m.end() < len(anon) else " "
        # caporali sono già non-parola; ma controlla che intorno non ci
        # sia una lettera/numero attaccata alla stessa parola originale.
        # (I caporali stessi bastano come confine, quindi questa è una
        # sicurezza in più: nessuna lettera "leftover" appiccicata.)
        assert not (prima.isalnum() and dopo.isalnum()), (
            f"placeholder {m.group()!r} sembra spezzare una parola: "
            f"prima={prima!r} dopo={dopo!r}"
        )


def test_g2_no_span_attraverso_newline(vault_temp):
    """Nessun segnaposto contiene un a-capo (bug reale sui PDF con tabelle)."""
    testo = (
        "Nome:\nMario Rossi\nAzienda:\nBeta srl\n"
        "Contatto:\nmario.rossi@example.com\n"
    )
    anon, _ = anonimizza(testo, "s2b", db_path=vault_temp)
    for m in PH_RE.finditer(anon):
        assert "\n" not in m.group(), f"placeholder attraversa newline: {m.group()!r}"


def test_g2_nessuno_scambio(vault_temp):
    """Con 30 entità distinte, ogni segnaposto viene emesso una sola volta."""
    persone = [f"Persona{i} Cognome{i}" for i in range(30)]
    testo = ". ".join(f"{p} lavora qui" for p in persone) + "."
    _, entita = anonimizza(testo, "s2c", db_path=vault_temp)
    placeholder = [e["placeholder"] for e in entita if e.get("placeholder")]
    assert len(placeholder) == len(set(placeholder)), "placeholder duplicati emessi"


# ---------------------------------------------------------------------------
# G3 — Zero fughe strutturati (validatore aritmetico)
# ---------------------------------------------------------------------------

# IBAN italiani (mod-97 validi), CF, PIVA, email, telefono, carta.
VALORI_STRUTTURATI = [
    ("IBAN", "IT60X0542811101000000123456"),
    ("IBAN", "IT28W8000000292100645211151"),
    ("CF",   "RSSMRA80A01H501U"),
    ("CF",   "BNCLGU75E15F205X"),
    ("EMAIL", "mario.rossi@example.com"),
    ("EMAIL", "info@azienda-italiana.it"),
    ("TELEFONO", "+39 333 1234567"),
    ("TELEFONO", "+39 06 12345678"),
    ("CARTA", "4111 1111 1111 1111"),
]


def test_g3_dati_strutturati_sempre_catturati(vault_temp):
    """Tutti i valori con validatore aritmetico devono essere sostituiti."""
    fughe: list[tuple[str, str]] = []
    for tipo, valore in VALORI_STRUTTURATI:
        testo = f"Il valore da verificare è {valore} e basta."
        anon, _ = anonimizza(testo, f"s3_{tipo}_{hash(valore)}", db_path=vault_temp)
        if valore in anon:
            fughe.append((tipo, valore))
    assert not fughe, f"fughe strutturate: {fughe}"


# ---------------------------------------------------------------------------
# G4 — Ripristino esatto (roundtrip byte per byte)
# ---------------------------------------------------------------------------

def test_g4_roundtrip_esatto(vault_temp):
    testi = [
        "Gentile Mario Rossi, l'appuntamento è confermato.",
        "IBAN IT60X0542811101000000123456, CF RSSMRA80A01H501U.",
        "Email mario.rossi@example.com, tel +39 333 1234567.",
        # Testo con caratteri speciali e emoji.
        "Ciao, sono Anna! 🌸 email: anna@test.it (importante).",
    ]
    for i, testo in enumerate(testi):
        anon, _entita = anonimizza(testo, f"s4_{i}", db_path=vault_temp)
        restored, _ = deanonimizza(anon, f"s4_{i}", db_path=vault_temp)
        assert restored == testo, (
            f"roundtrip non esatto per testo #{i}:\n"
            f"  originale:  {testo!r}\n"
            f"  ripristinato: {restored!r}"
        )


def test_g4_roundtrip_forme_diverse_stessa_persona(vault_temp):
    """Regressione bug fusione (2026-07-30): quando il testo contiene
    la stessa persona in forme diverse ("Mario Rossi" + "Rossi"), il
    ripristino DEVE tornare byte-identico. Prima del fix il vault
    fondeva le forme sotto lo stesso placeholder e il ripristino
    trasformava "Rossi" in "Mario Rossi", alterando il testo."""
    casi = [
        "Mario Rossi ha firmato. Poi Rossi ha aggiunto una nota.",
        "Mario Rossi cammina e incontra Andrea.",
        "Edilservice S.p.A. conferma. Edilservice spedisce.",
        "a giugno 2026 vado al mare, torno il 20 giugno",
        # Case diverso: forme distinte, ripristino byte-identico.
        "MARIO ROSSI ha firmato. Mario Rossi conferma.",
        # Due omonimi.
        "Mario Rossi e Luigi Rossi sono cugini",
        # Titolo onorifico → forme diverse.
        "Il Dott. Mario Rossi ha firmato. Mario Rossi conferma.",
    ]
    for i, testo in enumerate(casi):
        anon, _ = anonimizza(
            testo, f"s4b_{i}", db_path=vault_temp,
            categorie_attive={"PERSONA", "ORG"},
        )
        restored, _ = deanonimizza(anon, f"s4b_{i}", db_path=vault_temp)
        assert restored == testo, (
            f"[caso {i}] roundtrip non esatto:\n"
            f"  originale:    {testo!r}\n"
            f"  anonimizzato: {anon!r}\n"
            f"  ripristinato: {restored!r}"
        )


# ---------------------------------------------------------------------------
# G5 — Segnaposto coerenti (stessa entità → stesso segnaposto)
# ---------------------------------------------------------------------------

def test_g5_coerenza_entro_sessione(vault_temp):
    testo = (
        "Mario Rossi ha chiamato. Poi Mario Rossi ha scritto. "
        "L'email di Mario Rossi è mario.rossi@example.com. "
        "L'email mario.rossi@example.com è la stessa."
    )
    anon, entita = anonimizza(testo, "s5a", db_path=vault_temp)
    # "Mario Rossi" appare 3 volte: deve avere UN solo placeholder.
    ph_persona = [e["placeholder"] for e in entita
                  if e["valore_reale"] == "Mario Rossi" and e.get("placeholder")]
    assert len(ph_persona) == 1, f"Mario Rossi ha ricevuto {len(ph_persona)} placeholder distinti"
    assert anon.count(ph_persona[0]) == 3, (
        f"placeholder {ph_persona[0]} atteso 3 volte, trovato {anon.count(ph_persona[0])}"
    )


def test_g5_coerenza_tra_chiamate(vault_temp):
    """Anonimizzando due testi diversi nella stessa sessione, l'entità
    condivisa mantiene lo stesso segnaposto."""
    _a1, e1 = anonimizza("Il progetto è di Mario Rossi.", "s5b", db_path=vault_temp)
    _a2, e2 = anonimizza("Mario Rossi ha firmato oggi.", "s5b", db_path=vault_temp)
    ph1 = next((e["placeholder"] for e in e1 if e["valore_reale"] == "Mario Rossi"), None)
    ph2 = next((e["placeholder"] for e in e2 if e["valore_reale"] == "Mario Rossi"), None)
    assert ph1 and ph2, "Mario Rossi non è stato sostituito in una delle due chiamate"
    assert ph1 == ph2, (
        f"stessa entità, sessione, chiamate diverse → placeholder diversi: "
        f"{ph1!r} vs {ph2!r}"
    )


# ---------------------------------------------------------------------------
# G6 — Mai silenzioso (ogni sostituzione appare nella lista)
# ---------------------------------------------------------------------------

def test_g6_ogni_sostituzione_visibile(vault_temp):
    """Ogni segnaposto emesso nel testo deve avere una voce corrispondente
    nella lista entità (non-suggeriti)."""
    testo = (
        "Gentile Mario Rossi, l'IBAN IT60X0542811101000000123456 è confermato. "
        "Contatta luigi.bianchi@example.com o Anna Verdi. "
        "CF: RSSMRA80A01H501U, tel +39 333 1234567."
    )
    anon, entita = anonimizza(testo, "s6", db_path=vault_temp)
    ph_nel_testo = {m.group() for m in PH_RE.finditer(anon)}
    ph_nella_lista = {e["placeholder"] for e in entita
                      if e.get("placeholder") and not e.get("suggerito")}
    mancanti = ph_nel_testo - ph_nella_lista
    assert not mancanti, (
        f"segnaposto nel testo ma NON dichiarati nella lista entità: {mancanti}"
    )


# ---------------------------------------------------------------------------
# PARTE 4 (2026-07-31) — le garanzie rafforzate con i casi difficili
# ---------------------------------------------------------------------------

_DOCS_REALI = Path(__file__).resolve().parent.parent / "benchmark" / "documenti_utente"


def _testo_reale(nome: str, max_char: int | None = None) -> str:
    """Testo di un documento reale dell'utente (skip se assente)."""
    p = _DOCS_REALI / nome
    if not p.exists():
        pytest.skip(f"documento reale assente: {nome}")
    from backend.documenti import carica
    testo, _ = carica(str(p))
    return testo[:max_char] if max_char else testo


def test_g1_deterministico_dopo_riavvio(vault_temp):
    """G1 rafforzata: stesso risultato anche dopo il 'riavvio'
    dell'analyzer (reset + ricostruzione, come alla riapertura
    dell'app) su un estratto di documento reale."""
    from backend.motore import reset_analyzer
    testo = _testo_reale("hetepi_simulato.txt")
    a1, e1 = anonimizza(testo, "g1r", db_path=vault_temp)
    reset_analyzer()
    try:
        a2, e2 = anonimizza(testo, "g1r", db_path=vault_temp)
    finally:
        pass
    assert a1 == a2, "output diverso dopo riavvio dell'analyzer"
    n1 = sorted((e["tipo"], e["valore_reale"]) for e in e1)
    n2 = sorted((e["tipo"], e["valore_reale"]) for e in e2)
    assert n1 == n2


def test_g1_deterministico_documento_lungo(vault_temp):
    """G1 su documento lungo reale (estratto 20k char, due esecuzioni)."""
    testo = _testo_reale("Hetepi_Agent_AI.pdf", max_char=20_000)
    a1, _ = anonimizza(testo, "g1l", db_path=vault_temp)
    a2, _ = anonimizza(testo, "g1l", db_path=vault_temp)
    assert a1 == a2


def test_g1_analisi_a_blocchi_equivalente(vault_temp, monkeypatch):
    """L'analisi a blocchi (testi lunghi) produce lo stesso risultato
    dell'analisi monolitica: il taglio avviene su un a-capo e nessuno
    span può attraversarlo (invariante BUG-real 1)."""
    from backend import motore as _m
    testo = (
        "Il sig. Mario Rossi, CF RSSMRA80A01H501U, ha scritto.\n"
        "L'IBAN è IT60X0542811101000000123456 come da contratto.\n"
        "Contatti: mario.rossi@example.com, cell. 3391234567.\n"
    ) * 6
    a_mono, e_mono = anonimizza(testo, "g1b_m", db_path=vault_temp)
    monkeypatch.setattr(_m, "_MAX_BLOCK", 120)
    a_blk, e_blk = anonimizza(testo, "g1b_b", db_path=vault_temp)
    assert a_blk.replace("g1b_b", "") == a_mono.replace("g1b_m", "")
    n_m = sorted((e["tipo"], e["valore_reale"]) for e in e_mono)
    n_b = sorted((e["tipo"], e["valore_reale"]) for e in e_blk)
    assert n_m == n_b


def test_g2_tabella_e_due_colonne(vault_temp):
    """G2 rafforzata: tabelle e testo a due colonne — nessuna
    sostituzione a metà parola, nessuno span attraverso l'a-capo."""
    casi = [
        # Tabella con tab.
        ("Nome\tEmail\tCF\n"
         "Mario Rossi\tm.rossi@studio.it\tRSSMRA80A01H501U\n"
         "Luisa Verdi\tl.verdi@studio.it\tVRDLSU75E55F205X\n"),
        # Due colonne lette in verticale (righe adiacenti scorrelate).
        ("Mario Rossi          Fattura n. 2024/151\n"
         "via Roma 12            Importo: 1.200 EUR\n"
         "06081 Assisi           Scadenza: 30 giorni\n"),
    ]
    for i, testo in enumerate(casi):
        anon, _ = anonimizza(testo, f"g2t_{i}", db_path=vault_temp)
        for m in PH_RE.finditer(anon):
            assert "\n" not in m.group()
            prima = anon[m.start() - 1] if m.start() > 0 else " "
            dopo = anon[m.end()] if m.end() < len(anon) else " "
            assert not (prima.isalnum() and dopo.isalnum()), (
                f"[caso {i}] placeholder spezza una parola in {anon!r}"
            )
        # Il numero di righe non cambia mai.
        assert anon.count("\n") == testo.count("\n"), (
            f"[caso {i}] il numero di righe è cambiato"
        )


def test_g2_output_ocr_non_corrotto(vault_temp):
    """G2 su testo tipo-OCR (caratteri confusi, spazi anomali): il
    motore non deve corrompere ciò che non sostituisce."""
    testo = ("VERBALE Dl SEQUESTRO\n"           # "Dl" = OCR di "DI"
             "ll sottoscritto Mario Rossi , nato a Roma ,\n"
             "c0dice fiscale RSSMRA80A01H501U dichiara quanto segue .")
    anon, _ = anonimizza(testo, "g2o", db_path=vault_temp)
    restored, _ = deanonimizza(anon, "g2o", db_path=vault_temp)
    assert restored == testo


# Tutte le scritture ammesse dei tipi con validatore deterministico.
VALORI_STRUTTURATI_ESTESI = [
    ("IBAN-gruppi", "IT60 X054 2811 1010 0000 0123 456"),
    ("IBAN-minuscolo", "it60x0542811101000000123456"),
    ("IBAN-estero", "DE89370400440532013000"),
    ("CF-minuscolo", "rssmra80a01h501u"),
    ("PIVA-keyword", "P.IVA 01234567890"),
    ("TELEFONO-0039", "0039 333 1234567"),
    ("TELEFONO-trattini", "333-123-4567"),
    ("TARGA", "FG771XD"),
    ("TARGA-spazi", "FG 771 XD"),
    ("TARGA-minuscola", "fg771xd"),
    ("EMAIL-maiuscola", "MARIO.ROSSI@PEC.STUDIO.IT"),
]


def test_g3_strutturati_ogni_scrittura(vault_temp):
    """G3 rafforzata: ogni tipo deterministico in OGNI scrittura ammessa."""
    fughe = []
    for tipo, valore in VALORI_STRUTTURATI_ESTESI:
        testo = f"Il valore di riferimento è {valore} come da accordi."
        anon, _ = anonimizza(testo, f"g3e_{tipo}", db_path=vault_temp)
        cuore = valore.split()[-1] if tipo.startswith("PIVA") else valore
        if cuore in anon:
            fughe.append((tipo, valore))
    assert not fughe, f"fughe strutturate: {fughe}"


def test_g4_roundtrip_documenti_reali_interi(vault_temp):
    """G4 rafforzata: byte-per-byte su documenti reali INTERI, non frasi."""
    for nome in ("hetepi_simulato.txt", "README.md"):
        testo = _testo_reale(nome)
        sid = f"g4r_{nome}"
        anon, _ = anonimizza(testo, sid, db_path=vault_temp)
        restored, _ = deanonimizza(anon, sid, db_path=vault_temp)
        assert restored == testo, f"roundtrip non esatto su {nome}"


def test_g4_roundtrip_atto_legale_intero(vault_temp):
    """G4 sul documento di mercato: l'atto d'appello reale (47k char,
    32+ entità), byte-per-byte."""
    testo = _testo_reale("Atto_giudiziario.pdf")
    anon, _ = anonimizza(testo, "g4a", db_path=vault_temp)
    restored, _ = deanonimizza(anon, "g4a", db_path=vault_temp)
    assert restored == testo


def test_g4_span_persona_non_ingoia_contesto_anagrafico(vault_temp):
    """Regressione 2026-08-02: il neurale inglobava "nato" (e la
    preposizione "a"/"ad" successiva) dentro lo span PERSONA. Effetti:

    - la parola sparisce dall'uscita anonimizzata: il downstream perde
      il contesto anagrafico ("«PERSONA» ad «LUOGO_NASCITA»" invece di
      "«PERSONA» nato ad «LUOGO_NASCITA»");
    - "nato a/il" è **l'indicatore di contesto** usato dal recognizer
      LUOGO_NASCITA / DATA_NASCITA per innescarsi: se resta dentro
      PERSONA, un innesco vive dentro lo span del vicino;
    - G4 (roundtrip byte-identico) *sembra* tenere solo grazie al
      valore memorizzato in vault — ma qualunque modifica manuale
      dell'utente (correzione, spostamento, riordino) romperebbe il
      testo perché la parola "nato" non è più visibile per essere
      riconosciuta come contesto.

    Il test verifica sia la struttura dello span (non deve contenere
    parole di contesto anagrafico o preposizioni al bordo) sia il
    roundtrip byte-identico.
    """
    from backend.motore import _PAROLE_CONTESTO_ANAGRAFICO
    casi = [
        "Ciao sono Matteo Rossi nato a Roma il 15 maggio 1975",
        "Mario Rossi nato a Milano il 3/4/1990",
        "La sig.ra Anna Verdi residente a Bologna in via Roma 5",
        "Giuseppe Bianchi domiciliato in Torino",
        "Luca Bianchi originario di Napoli",
        "Maria Rossi coniugata Bianchi",
        "Il paziente Mario Rossi nato a Perugia il 15/1/1985 richiede",
    ]
    for i, testo in enumerate(casi):
        sid = f"g4pers_{i}"
        anon, entita = anonimizza(testo, sid, db_path=vault_temp)
        restored, _ = deanonimizza(anon, sid, db_path=vault_temp)
        assert restored == testo, (
            f"[caso {i}] roundtrip non esatto:\n"
            f"  originale:    {testo!r}\n"
            f"  anonimizzato: {anon!r}\n"
            f"  ripristinato: {restored!r}"
        )
        for e in entita:
            if e.get("tipo") != "PERSONA":
                continue
            valore = (e.get("valore_reale") or "").strip()
            for tok in re.split(r"\s+", valore):
                tok_lc = tok.strip(".,;:!?«»\"'()").lower()
                assert tok_lc not in _PAROLE_CONTESTO_ANAGRAFICO, (
                    f"[caso {i}] span PERSONA contiene la parola di "
                    f"contesto anagrafico {tok_lc!r}:\n"
                    f"  originale:    {testo!r}\n"
                    f"  span:         {valore!r}\n"
                    f"  anonimizzato: {anon!r}"
                )


def test_g4_testo_che_contiene_gia_un_segnaposto(vault_temp):
    """G4 quando l'originale contiene già qualcosa che sembra un segnaposto.

    Il ripristino accetta il segnaposto anche nudo o decorato diversamente
    perché i modelli linguistici lo riformattano. Di conseguenza un testo
    che contiene per conto suo "[CF_1]" — capita in ogni documento che
    parla di anonimizzazione, ed è stato trovato su un PDF reale
    dell'utente — rischia di vederselo espandere in un codice fiscale vero
    che lì non c'era. L'assegnazione salta i numeri già occupati.
    """
    testo = (
        "Lo strumento sostituisce ogni dato con un segnaposto stabile "
        "([FULLNAME_1], [IBAN_1], [CF_1]) e tiene la corrispondenza su "
        "disco.\nEsempio reale: Mario Rossi, codice fiscale "
        "RSSMRA85H12F205Z, IBAN IT60X0542811101000000123456."
    )
    anon, entita = anonimizza(testo, "g4ph", db_path=vault_temp)
    restored, _ = deanonimizza(anon, "g4ph", db_path=vault_temp)
    assert restored == testo, (
        "il segnaposto già presente nell'originale è stato espanso.\n"
        f"originale:    {testo!r}\nripristinato: {restored!r}"
    )
    assegnati = {e["placeholder"] for e in entita if e.get("placeholder")}
    assert "«CF_1»" not in assegnati, (
        f"«CF_1» assegnato benché il testo contenga già [CF_1]: {assegnati}"
    )


def test_g5_forme_diverse_placeholder_diversi(vault_temp):
    """G5 rafforzata nei due sensi: stessa forma → stesso segnaposto;
    forme scritte diverse → segnaposto diversi (regola chiave-letterale)."""
    testo = ("Mario Rossi ha firmato. MARIO ROSSI è in intestazione. "
             "Mario Rossi conferma.")
    anon, entita = anonimizza(testo, "g5f", db_path=vault_temp)
    ph = {e["valore_reale"]: e["placeholder"] for e in entita
          if e.get("placeholder")}
    assert ph.get("Mario Rossi") and ph.get("MARIO ROSSI")
    assert ph["Mario Rossi"] != ph["MARIO ROSSI"], (
        "forme scritte diverse devono avere segnaposto diversi (G4 dipende da questo)"
    )
    assert anon.count(ph["Mario Rossi"]) == 2


def test_g6_documento_reale_tutte_in_tabella(vault_temp):
    """G6 rafforzata: su un documento reale, ogni segnaposto presente
    nel testo anonimizzato ha la sua riga nella lista entità."""
    testo = _testo_reale("hetepi_simulato.txt")
    anon, entita = anonimizza(testo, "g6r", db_path=vault_temp)
    nel_testo = {m.group() for m in PH_RE.finditer(anon)}
    in_lista = {e["placeholder"] for e in entita
                if e.get("placeholder") and not e.get("suggerito")}
    assert nel_testo <= in_lista, (
        f"segnaposto senza riga in tabella: {nel_testo - in_lista}"
    )


# ---------------------------------------------------------------------------
# Riepilogo eseguibile a mano — python -m tests.test_garanzie
# ---------------------------------------------------------------------------

def _riepilogo():
    """Stampa un riepilogo leggibile delle sei garanzie."""
    print("PrivacyBridge — Verifica delle sei garanzie di prodotto")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmp:
        vault = os.path.join(tmp, "garanzie.db")
        casi = [
            ("G1  Deterministico",        test_g1_deterministico),
            ("G2a No metà parola",        test_g2_no_metà_parola),
            ("G2b No newline nei ph",     test_g2_no_span_attraverso_newline),
            ("G2c No scambio placeholder", test_g2_nessuno_scambio),
            ("G3  Zero fughe strutturati", test_g3_dati_strutturati_sempre_catturati),
            ("G4  Roundtrip esatto",       test_g4_roundtrip_esatto),
            ("G4b Forme diverse stessa persona", test_g4_roundtrip_forme_diverse_stessa_persona),
            ("G5a Coerenza in sessione",   test_g5_coerenza_entro_sessione),
            ("G5b Coerenza tra chiamate",  test_g5_coerenza_tra_chiamate),
            ("G6  Mai silenzioso",         test_g6_ogni_sostituzione_visibile),
        ]
        ok = 0
        ko = 0
        for nome, funz in casi:
            try:
                funz(vault)
                print(f"  ✓ {nome}")
                ok += 1
            except AssertionError as e:
                print(f"  ✗ {nome}\n     {e}")
                ko += 1
    print("=" * 60)
    print(f"Totale: {ok + ko}   OK: {ok}   FALLITI: {ko}")
    return ko == 0


if __name__ == "__main__":
    ok = _riepilogo()
    sys.exit(0 if ok else 1)
