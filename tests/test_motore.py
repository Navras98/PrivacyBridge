# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Test del motore di anonimizzazione."""

from __future__ import annotations

import os
import uuid

import pytest

from backend.motore import anonimizza, deanonimizza, get_analyzer
from backend.vault import Vault

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _warm_analyzer():
    """Costruisce l'analyzer una sola volta per tutta la suite."""
    get_analyzer()
    yield


@pytest.fixture
def tmp_db(tmp_path):
    path = tmp_path / "vault.db"
    return str(path)


@pytest.fixture
def sessione():
    return "sess-" + uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Helper: costruttore IBAN italiano valido
# ---------------------------------------------------------------------------

def _iban_check_digits(bban: str) -> str:
    numeric = ""
    for ch in bban + "IT00":
        numeric += ch if ch.isdigit() else str(ord(ch) - 55)
    check = 98 - (int(numeric) % 97)
    return f"{check:02d}"


def _make_iban(bban: str = "X0542811101000000123456") -> str:
    check = _iban_check_digits(bban)
    return f"IT{check}{bban}"


# ---------------------------------------------------------------------------
# 1. Nome italiano rilevato
# ---------------------------------------------------------------------------

def test_nome_italiano_rilevato(tmp_db, sessione):
    testo = "Il cliente Mario Rossi ha firmato il contratto."
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)

    assert "Mario Rossi" not in out
    assert "«PERSONA_1»" in out

    personas = [e for e in ents if e["tipo"] == "PERSONA"]
    assert len(personas) == 1
    assert personas[0]["valore_reale"] == "Mario Rossi"
    assert personas[0]["placeholder"] == "«PERSONA_1»"


# ---------------------------------------------------------------------------
# 2. Email, telefono, IBAN, CF, P.IVA rilevati
# ---------------------------------------------------------------------------

def test_pii_multiple_rilevate(tmp_db, sessione):
    iban = _make_iban()
    cf = "RSSMRA80A01H501U"     # valido
    piva = "12345678903"        # valido
    testo = (
        f"Contatti: email mario.rossi@example.com, telefono +39 333 1234567. "
        f"IBAN: {iban}. Codice fiscale {cf}. Partita IVA: {piva}."
    )
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)

    tipi = {e["tipo"] for e in ents}
    # Ci aspettiamo almeno queste categorie:
    for atteso in ("EMAIL", "TELEFONO", "IBAN", "CF", "PIVA"):
        assert atteso in tipi, f"tipo {atteso} non rilevato. tipi={tipi}"

    # Nessuno dei valori originali deve comparire nel testo anonimizzato.
    for valore in [
        "mario.rossi@example.com",
        "+39 333 1234567",
        iban,
        cf,
        piva,
    ]:
        assert valore not in out, f"{valore} presente nel testo anonimizzato"


# ---------------------------------------------------------------------------
# 3. Round-trip (identità)
# ---------------------------------------------------------------------------

def test_round_trip_identita(tmp_db, sessione):
    testo = (
        "Buongiorno, sono Mario Rossi (email: mario@example.com). "
        f"Il mio IBAN è {_make_iban()}. Codice fiscale RSSMRA80A01H501U."
    )
    anon, _ = anonimizza(testo, sessione, db_path=tmp_db)
    restored, report = deanonimizza(anon, sessione, db_path=tmp_db)

    assert restored == testo
    assert report["warning"] == []


# ---------------------------------------------------------------------------
# 4. Coerenza: stesso nome N volte → stesso placeholder
# ---------------------------------------------------------------------------

def test_coerenza_stesso_nome(tmp_db, sessione):
    frase = "Mario Rossi conferma la sua presenza. "
    testo = frase * 20  # Mario Rossi 20 volte
    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)

    personas = [e for e in ents if e["tipo"] == "PERSONA"]
    assert len(personas) == 1
    assert personas[0]["placeholder"] == "«PERSONA_1»"
    assert personas[0]["occorrenze"] == 20

    # Il testo anonimizzato deve contenere «PERSONA_1» esattamente 20 volte.
    assert anon.count("«PERSONA_1»") == 20
    assert "Mario Rossi" not in anon


# ---------------------------------------------------------------------------
# 5. Non-confusione: 100 nomi diversi → 100 placeholder distinti
# ---------------------------------------------------------------------------

_FIRST = [
    "Mario", "Luigi", "Giovanni", "Paolo", "Francesco", "Andrea", "Marco",
    "Antonio", "Alessandro", "Roberto",
]
_LAST = [
    "Rossi", "Bianchi", "Verdi", "Neri", "Ferrari", "Colombo", "Ricci",
    "Marino", "Greco", "Bruno",
]


def _cento_nomi():
    nomi = []
    for f in _FIRST:
        for l in _LAST:
            nomi.append(f"{f} {l}")
    assert len(nomi) == 100
    assert len(set(nomi)) == 100
    return nomi


def test_cento_nomi_distinti(tmp_db, sessione):
    nomi = _cento_nomi()
    righe = [f"Il cliente {n} ha firmato il documento." for n in nomi]
    testo = "\n".join(righe)

    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)

    personas = [e for e in ents if e["tipo"] == "PERSONA"]
    valori_persona = {e["valore_reale"] for e in personas}
    placeholders = {e["placeholder"] for e in personas}

    # Tutti i 100 nomi devono comparire come entità distinte...
    assert valori_persona == set(nomi), (
        f"nomi mancanti: {set(nomi) - valori_persona} — "
        f"nomi in eccesso: {valori_persona - set(nomi)}"
    )
    # ...con placeholder tutti diversi.
    assert len(placeholders) == 100

    # Nessun nome originale nel testo anonimizzato.
    for n in nomi:
        assert n not in anon

    # Round-trip.
    restored, report = deanonimizza(anon, sessione, db_path=tmp_db)
    assert restored == testo
    assert report["warning"] == []
    # Nessuna confusione: ogni placeholder ripristina il PROPRIO valore.
    for n in nomi:
        assert n in restored


# ---------------------------------------------------------------------------
# 6. Persistenza attraverso chiusura/riapertura del vault
# ---------------------------------------------------------------------------

def test_persistenza_sessione(tmp_db, sessione):
    testo = "Il signor Mario Rossi vive a Roma."
    v1 = Vault(tmp_db)
    anon, _ = anonimizza(testo, sessione, vault=v1)
    v1.close()

    # Nuova istanza vault -> stesso file DB.
    v2 = Vault(tmp_db)
    restored, report = deanonimizza(anon, sessione, vault=v2)
    v2.close()

    assert restored == testo
    assert report["warning"] == []


# ---------------------------------------------------------------------------
# 7. Testo lungo (> 100k caratteri) — coerenza tra blocchi
# ---------------------------------------------------------------------------

def test_testo_lungo_coerenza(tmp_db, sessione):
    # Uso nomi "puri" (non ambigui col vocabolario italiano) — la nuova
    # validazione dizionario post-neurale richiede almeno un token noto
    # non-in-vocab per accettare uno span PERSON. Nomi come "Marco" o
    # "Colombo" (in vocab per omonimia) da soli non passano.
    nomi = [
        "Mario Rossi", "Luigi Bianchi", "Anna Verdi", "Paolo Neri",
        "Giulia Ferrari", "Simone Rizzo", "Francesca Ricci",
        "Roberto Zanetti", "Filippo Conti", "Giorgia Marino",
    ]
    # Costruisco un testo > 100k caratteri con 30 nomi distinti * 10 occorrenze.
    # Uso 3 gruppi da 10 nomi + padding minimo per superare la soglia.
    tutti_nomi = []
    for suffix in ("A", "B", "C"):
        for base in nomi:
            first, last = base.split()
            tutti_nomi.append(f"{first} {last}{suffix}")
    assert len(tutti_nomi) == 30

    frasi = []
    # Padding ridotto al minimo per superare 100k char: ~315 char per padding × 300 occorrenze.
    padding = "Il contratto è stato redatto in conformità alle norme vigenti. " * 5
    for _ in range(10):
        for nm in tutti_nomi:
            frasi.append(f"Il cliente {nm} ha firmato il contratto.")
            frasi.append(padding)
    testo = "\n".join(frasi)

    # Deve superare i 100k caratteri (soglia _MAX_BLOCK).
    assert len(testo) > 100_000

    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)

    personas = [e for e in ents if e["tipo"] == "PERSONA"]
    valori = {e["valore_reale"] for e in personas}
    assert valori == set(tutti_nomi), (
        f"mancanti: {set(tutti_nomi) - valori}; eccesso: {valori - set(tutti_nomi)}"
    )
    # Ogni nome deve avere placeholder unico e stabile.
    assert len({e["placeholder"] for e in personas}) == 30
    # Ogni nome ripetuto 10 volte.
    for e in personas:
        assert e["occorrenze"] == 10

    # Round-trip.
    restored, report = deanonimizza(anon, sessione, db_path=tmp_db)
    assert restored == testo
    assert report["warning"] == []


# ---------------------------------------------------------------------------
# 8. Testo senza entità → identico
# ---------------------------------------------------------------------------

def test_testo_senza_entita(tmp_db, sessione):
    """Nessuna sostituzione attiva su testo comune; sono ammessi
    suggerimenti (livello 3, non modificano il testo). "Gatto" e
    "Camino" sono cognomi italiani veri: il post-truecasing li rileva
    come suggerimenti — l'utente decide se accettarli in tabella."""
    testo = "il gatto dorme sul tappeto rosso vicino al camino acceso."
    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert anon == testo   # nessuna sostituzione nel testo
    attivi = [e for e in ents if not e.get("suggerito")]
    assert attivi == []    # nessuna entità attiva

    restored, report = deanonimizza(anon, sessione, db_path=tmp_db)
    assert restored == testo
    assert report["ripristinati"] == []
    assert report["non_trovati"] == []
    assert report["warning"] == []


# ---------------------------------------------------------------------------
# 9. Placeholder ignoto nel testo → lasciato invariato e segnalato
# ---------------------------------------------------------------------------

def test_placeholder_sconosciuto(tmp_db, sessione):
    testo = "Buongiorno, sono Mario Rossi."
    anon, _ = anonimizza(testo, sessione, db_path=tmp_db)
    # anon contiene «PERSONA_1». Inserisco un placeholder ignoto.
    finto = anon + " Riferimento aggiuntivo: «PERSONA_99»."
    restored, report = deanonimizza(finto, sessione, db_path=tmp_db)

    # «PERSONA_99» non è stato mai emesso: deve restare invariato.
    assert "«PERSONA_99»" in restored
    assert "«PERSONA_99»" in report["warning"]

    # «PERSONA_1» deve essere stato ripristinato.
    assert "Mario Rossi" in restored
    assert "«PERSONA_1»" in report["ripristinati"]
    # Non deve MAI aver sostituito PERSONA_99 con il valore di PERSONA_1.
    assert restored.count("Mario Rossi") == 1


# ---------------------------------------------------------------------------
# 10. Guardia di non-confusione tra due placeholder diversi
# ---------------------------------------------------------------------------

def test_non_confusione_placeholder(tmp_db, sessione):
    testo = (
        "Gentile Dott. Mario Rossi, la informiamo che il colloquio con "
        "Luigi Bianchi è confermato."
    )
    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)
    personas = [e for e in ents if e["tipo"] == "PERSONA"]
    # Devono essere due placeholder distinti.
    ph_map = {e["placeholder"]: e["valore_reale"] for e in personas}
    assert len(ph_map) == 2

    restored, _ = deanonimizza(anon, sessione, db_path=tmp_db)
    # Ogni placeholder è tornato al PROPRIO valore.
    for val in ph_map.values():
        assert val in restored


def test_non_confusione_placeholder_senza_keywords(tmp_db, sessione):
    """Regressione: la vecchia formulazione del test cadeva su inglese
    perché il router di lingua non trovava keyword italiane. Con router
    default-italiano ora deve trovare entrambe le persone anche qui.
    """
    testo = "Mario Rossi e Luigi Bianchi lavorano insieme."
    _anon, ents = anonimizza(testo, sessione, db_path=tmp_db)
    personas = [e for e in ents if e["tipo"] == "PERSONA"]
    ph_map = {e["placeholder"]: e["valore_reale"] for e in personas}
    assert len(ph_map) == 2, f"attese 2 persone distinte, trovate {ph_map}"


def test_forza_lingua_italiano(tmp_db, sessione):
    """L'override esplicito lingua='it' deve avere la precedenza."""
    testo = "Please contact Mario Rossi about the meeting tomorrow."
    _anon, ents = anonimizza(testo, sessione, db_path=tmp_db, lingua="it")
    personas = [e for e in ents if e["tipo"] == "PERSONA"]
    assert any(p["valore_reale"] == "Mario Rossi" for p in personas)


# ---------------------------------------------------------------------------
# 11. Interruzione sicura: eccezione durante anonimizzazione → nessun dato
#     parziale persistito nel vault.
# ---------------------------------------------------------------------------

def test_interruzione_sicura(monkeypatch, tmp_db, sessione):
    """Verifica che un'interruzione a metà elaborazione non lasci dati parziali."""
    # 1. Testo lungo con molte entità.
    nomi = ["Mario Rossi", "Luigi Bianchi", "Anna Verdi", "Paolo Neri",
            "Giulia Ferrari", "Marco Colombo", "Francesca Ricci"]
    pad = "Il documento riporta le seguenti informazioni contrattuali. " * 15
    frasi = []
    for _ in range(8):
        for nm in nomi:
            frasi.append(f"Il cliente {nm} ha firmato il contratto.")
            frasi.append(pad)
    testo = "\n".join(frasi)
    assert len(testo) > 50_000

    # 2. Simula interruzione: vault.add() solleva eccezione alla 3a chiamata.
    orig_add = Vault.add
    call_count = [0]

    def add_con_interruzione(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] >= 3:
            raise RuntimeError("Interruzione simulata dopo 2 entità")
        return orig_add(self, *args, **kwargs)

    monkeypatch.setattr(Vault, "add", add_con_interruzione)

    # 3. L'eccezione deve propagarsi senza restituire output parziale.
    with pytest.raises(RuntimeError, match="Interruzione simulata"):
        anonimizza(testo, sessione, db_path=tmp_db)

    # Ripristina il metodo originale per la verifica.
    monkeypatch.undo()

    # 4. Nessun output parziale restituito (l'eccezione è stata propagata).

    # 5. Il vault non contiene entità per questa sessione (rollback avvenuto).
    v = Vault(tmp_db)
    try:
        righe = list(v.all_for_session(sessione))
        assert len(righe) == 0, (
            f"Vault contiene {len(righe)} entità dopo interruzione: {righe}"
        )
    finally:
        v.close()


# ---------------------------------------------------------------------------
# 12. Nessuna chiamata di rete (R5): verifichiamo che l'analyzer costruito
#     stia lavorando senza contattare l'esterno — proxy: nessun socket
#     esterno dopo warmup. Test light: import osservabile.
# ---------------------------------------------------------------------------

def test_no_rete_su_anonimizza(monkeypatch, tmp_db, sessione):
    """Verifica che una chiamata a anonimizza non apra connessioni di rete."""
    import socket

    apri_calls = []

    def _blocked_connect(self, address, *args, **kwargs):
        apri_calls.append(address)
        raise OSError("Rete bloccata durante il test (R5)")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)

    testo = "Il cliente Mario Rossi ha inviato una email."
    anon, _ = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Mario Rossi" not in anon
    assert apri_calls == []


# ---------------------------------------------------------------------------
# BUG-N minuscolo (post GRUPPO B) — nomi/cognomi in lowercase con contesto
# ---------------------------------------------------------------------------

def test_bugn_minuscolo_caso_canonico(tmp_db, sessione):
    """'ciao sono matteo rossi' — nome+cognome minuscolo dopo 'sono'.
    Il cognome NON è nel dizionario, ma deve essere catturato perché
    il primo token è un nome noto (matteo)."""
    testo = "ciao sono matteo rossi, nato a roma il 15 maggio del 1975"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "matteo" not in out.lower().split(",")[0]
    assert "rossi" not in out.lower().split(",")[0]


def test_bugn_minuscolo_mi_chiamo(tmp_db, sessione):
    testo = "mi chiamo andrea rossi"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "andrea rossi" not in out.lower()


def test_bugn_minuscolo_dopo_ciao(tmp_db, sessione):
    testo = "ciao mario, ci vediamo dopo"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "mario" not in out.lower().split(",")[0]


def test_bugn_minuscolo_titolo(tmp_db, sessione):
    testo = "dott. rossi la ringrazio"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "rossi" not in out.lower()


def test_bugn_minuscolo_no_fp_aggettivo(tmp_db, sessione):
    """'sono felice' — felice è aggettivo, NON deve essere sostituito
    (anche se 'Felice' è un nome nel dizionario)."""
    testo = "sono felice del risultato di oggi"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert out == testo, f"'felice' non doveva essere sostituito: {out!r}"


# ---------------------------------------------------------------------------
# DATA_NASCITA — categoria dedicata attiva per default
# ---------------------------------------------------------------------------

def test_data_nascita_intera_catturata(tmp_db, sessione):
    """'nato a roma il 15 maggio del 1975' — la data intera va
    sostituita, incluso il giorno."""
    testo = "ciao sono matteo rossi, nato a roma il 15 maggio del 1975"
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    for parte in ["27 marzo del 2004", "27 marzo 2004", "marzo del 2004"]:
        assert parte not in out, (
            f"parte data '{parte}' non mascherata in: {out!r}"
        )
    dn = [e for e in ents if e["tipo"] == "DATA_NASCITA"]
    assert dn, f"nessuna DATA_NASCITA in {ents}"


def test_data_nascita_vari_formati(tmp_db, sessione):
    for testo, atteso in [
        ("nato il 15/06/1980", "15/06/1980"),
        ("Data di nascita: 3 aprile 1990", "3 aprile 1990"),
        ("nasce il 12 gennaio 2001 a Roma", "12 gennaio 2001"),
        ("nato a Roma il 12/03/1985", "12/03/1985"),
    ]:
        out, _ = anonimizza(testo, sessione + "-" + testo[:5],
                            db_path=tmp_db)
        assert atteso not in out, f"{testo!r}: {atteso!r} non mascherato in {out!r}"


def test_data_generica_spenta_per_default(tmp_db, sessione):
    """DATA (categoria) è spenta per default: date generiche NON toccate."""
    testo = "La riunione è il 15 marzo 2026"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "15 marzo 2026" in out


# ---------------------------------------------------------------------------
# LUOGO_NASCITA — categoria dedicata attiva per default
# ---------------------------------------------------------------------------

def test_luogo_nascita_caso_canonico(tmp_db, sessione):
    testo = "ciao sono matteo rossi, nato a roma il 15 maggio del 1975"
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "assisi" not in out
    ln = [e for e in ents if e["tipo"] == "LUOGO_NASCITA"]
    assert ln and ln[0]["valore_reale"].lower() == "roma"


def test_luogo_nascita_multi_parola(tmp_db, sessione):
    testo = "nata a Reggio Emilia il 3/4/1990"
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Reggio Emilia" not in out
    ln = [e for e in ents if e["tipo"] == "LUOGO_NASCITA"]
    assert ln and ln[0]["valore_reale"] == "Reggio Emilia"


def test_luogo_nascita_toponimo_composto(tmp_db, sessione):
    testo = "originario di San Giovanni Valdarno"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "San Giovanni Valdarno" not in out


def test_luogo_nascita_campo_etichetta(tmp_db, sessione):
    testo = "luogo di nascita: Milano"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Milano" not in out


def test_luogo_nascita_provincia(tmp_db, sessione):
    testo = "nato in provincia di Bari"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Bari" not in out


# ---------------------------------------------------------------------------
# Truecasing — pre-passaggio strutturale
# ---------------------------------------------------------------------------

def test_truecasing_cognome_con_particella(tmp_db, sessione):
    """'ciao sono stefania de giovanni abito a taranto' — cognome con
    particella 'de' (2 caratteri) in minuscolo, luogo di residenza
    (nuovo verbo 'abito'), tutto in minuscolo."""
    testo = "ciao sono stefania de giovanni abito a taranto"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "stefania" not in out.lower()
    assert "giovanni" not in out.lower()
    assert "taranto" not in out.lower()


def test_truecasing_multi_cognomi_con_particelle(tmp_db, sessione):
    testo = "mi chiamo giuseppe di marco, lavoro con anna della valle"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "giuseppe di marco" not in out.lower()
    assert "anna della valle" not in out.lower()


@pytest.mark.xfail(
    reason="'luca lo bianco' in minuscolo senza contesto forte: 'luca' viene "
    "catturato ma 'lo bianco' non viene incluso. Documentato in BLOCCHI.md § 10."
)
def test_truecasing_lo_bianco(tmp_db, sessione):
    testo = "scrivi a luca lo bianco per il preventivo"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "luca lo bianco" not in out.lower()


def test_truecasing_verbi_abitazione(tmp_db, sessione):
    for testo, atteso in [
        ("vivo a milano da 10 anni", "milano"),
        ("abito a taranto", "taranto"),
        ("risiedo a roma", "roma"),
    ]:
        out, _ = anonimizza(testo, sessione + "-" + testo[:5], db_path=tmp_db)
        assert atteso not in out.lower(), (
            f"{testo!r}: {atteso!r} non mascherato in {out!r}"
        )


def test_truecasing_no_fp_su_frasi_comuni(tmp_db, sessione):
    """Frasi minuscole con parole comuni: nessuna sostituzione attesa."""
    for testo in [
        "il gatto dorme sul tappeto rosso vicino al camino acceso.",
        "sono felice del risultato",
        "sto andando al mare",
        "sono contento del lavoro",
    ]:
        out, _ = anonimizza(testo, sessione + "-" + testo[:5], db_path=tmp_db)
        assert out == testo, (
            f"trap {testo!r}: modificato in {out!r}"
        )


def test_luogo_generico_spento_per_default(tmp_db, sessione):
    """LUOGO generico è spento: 'a Milano' senza contesto anagrafico
    NON viene toccato."""
    testo = "La riunione si tiene a Milano il 15 marzo 2026"
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Milano" in out
    assert "15 marzo 2026" in out


# ---------------------------------------------------------------------------
# GRUPPO A1 — Normalizzazione chiavi
# ---------------------------------------------------------------------------

def test_a1_normalizzazione_base_preserva_case():
    """Dopo il fix G4: _base_norm normalizza spazi + strip + punteggiatura
    ai bordi ma NON minuscolizza — case preservato così "MARIO ROSSI" e
    "Mario Rossi" hanno chiavi distinte (evita di alterare il ripristino)."""
    from backend.risoluzione import _base_norm
    assert _base_norm("  Mario Rossi  ") == "Mario Rossi"
    assert _base_norm("Mario\tRossi") == "Mario Rossi"
    assert _base_norm("«Mario Rossi»") == "Mario Rossi"
    assert _base_norm("MARIO ROSSI!") == "MARIO ROSSI"
    # Case distinct → chiavi distinte
    assert _base_norm("MARIO ROSSI") != _base_norm("Mario Rossi")


def test_a1_chiave_persona_conserva_titoli():
    """Dopo il fix G4: chiave_persona NON strippa più i titoli onorifici,
    così "Dott. Mario Rossi" e "Mario Rossi" hanno chiavi distinte e
    ricevono placeholder diversi. Motivo: il ripristino altrimenti
    trasformerebbe una forma nell'altra."""
    from backend.risoluzione import chiave_persona
    assert chiave_persona("Mario Rossi") == "Mario Rossi"
    assert chiave_persona("Dott. Mario Rossi") == "Dott. Mario Rossi"
    assert chiave_persona("Il Sig. Rossi") == "Il Sig. Rossi"
    # Forme diverse → chiavi diverse.
    assert chiave_persona("Mario Rossi") != chiave_persona("Rossi")
    assert chiave_persona("Mario Rossi") != chiave_persona("Dott. Mario Rossi")


def test_a1_chiave_org_conserva_forme_societarie():
    """Dopo il fix G4: chiave_org NON strippa più le forme societarie:
    "Edilservice S.p.A." e "Edilservice" sono forme diverse → chiavi
    diverse → placeholder distinti."""
    from backend.risoluzione import chiave_org
    assert chiave_org("Edilservice S.p.A.") == "Edilservice S.p.A"
    assert chiave_org("Edilservice") == "Edilservice"
    assert chiave_org("EDILSERVICE") == "EDILSERVICE"
    # Forme diverse → chiavi diverse.
    assert chiave_org("Edilservice S.p.A.") != chiave_org("Edilservice")
    assert chiave_org("Edilservice") != chiave_org("EDILSERVICE")


def test_a1_chiave_data_canonica():
    from backend.risoluzione import chiave_data
    # Formati numerici.
    assert chiave_data("19/06/2026") == "2026-06-19"
    assert chiave_data("19-06-2026") == "2026-06-19"
    assert chiave_data("2026-06-19") == "2026-06-19"
    # Formato testuale completo.
    assert chiave_data("19 giugno 2026") == "2026-06-19"
    assert chiave_data("19  Giugno  2026") == "2026-06-19"
    # Solo mese + anno.
    assert chiave_data("giugno 2026") == "2026-06-??"
    # Solo giorno + mese senza anno.
    assert chiave_data("4 giugno") == "????-06-04"
    # Diversi giorni stesso mese: chiavi distinte.
    assert chiave_data("19 giugno 2026") != chiave_data("giugno 2026")
    assert chiave_data("4 giugno") != chiave_data("giugno 2026")


# ---------------------------------------------------------------------------
# GRUPPO A2 — Risoluzione entità coerente end-to-end
# ---------------------------------------------------------------------------

def test_a2_stessa_data_4_formati_roundtrip_esatto(tmp_db, sessione):
    """SUPERATA il 2026-07-31 la regola "un placeholder per 4 formati":
    riusare lo stesso segnaposto per forme letterali diverse rompeva il
    ripristino byte-identico (G4) quando due formati convivevano nello
    stesso documento — caso reale trovato sull'atto OCR ("Andrea
    Rossi." col punto vs "Mario Rossi"). Ora ogni forma letterale
    ha il SUO segnaposto; la stessa forma continua a riusare lo stesso.
    Il vincolo che conta è il roundtrip esatto."""
    testo = (
        "Riunione confermata per il 19/06/2026. "
        "Come discusso il 19 giugno 2026 con il team. "
        "Data indicata: 19-06-2026. "
        "Vedi anche il verbale del 2026-06-19 e ancora il 19/06/2026."
    )
    out, ents = anonimizza(
        testo, sessione, db_path=tmp_db,
        categorie_attive={"DATA"},
    )
    date = [e for e in ents if e["tipo"] == "DATA"]
    # 4 forme letterali → 4 placeholder distinti; la quinta occorrenza
    # ("19/06/2026" ripetuta) riusa il placeholder della prima.
    assert len({e["placeholder"] for e in date}) == 4
    ripetuta = next(e for e in date if e["valore_reale"] == "19/06/2026")
    assert ripetuta["occorrenze"] == 2
    restored, _ = deanonimizza(out, sessione, db_path=tmp_db)
    assert restored == testo


def test_a2_persona_forme_diverse_placeholder_distinti(tmp_db, sessione):
    """Dopo il fix G4: forme scritte diverse della stessa persona ricevono
    placeholder distinti. Motivo: il ripristino sostituisce un placeholder
    con un solo valore; fondere "Mario Rossi" e "Rossi" trasformerebbe
    "Rossi" in "Mario Rossi" nel testo ripristinato, violando G4.

    Compensazione: l'informazione della correlazione è nel campo
    ``correlato_a`` di ciascuna entità (la UI la mostra in tabella).
    """
    testo = (
        "Il cliente Mario Rossi ha firmato il contratto. "
        "In seguito Rossi ha aggiunto una nota."
    )
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    persone = [e for e in ents if e["tipo"] == "PERSONA" and not e.get("suggerito")]
    # Se il recognizer prende sia "Mario Rossi" sia "Rossi", i placeholder
    # sono distinti; se prende solo "Mario Rossi", va bene lo stesso —
    # l'importante è che NON venga fusa "Rossi" sotto «PERSONA_1».
    valori = {e["valore_reale"] for e in persone}
    if "Rossi" in valori and "Mario Rossi" in valori:
        assert len({e["placeholder"] for e in persone
                    if e["valore_reale"] in {"Rossi", "Mario Rossi"}}) == 2, (
            f"forme diverse devono avere placeholder distinti: {persone}"
        )
    # Il testo ripristinato deve essere identico all'originale.
    rest, _ = deanonimizza(out, sessione, db_path=tmp_db)
    assert rest == testo, (
        f"roundtrip non esatto:\norig: {testo!r}\nrest: {rest!r}"
    )


def test_a2_azienda_forme_diverse_placeholder_distinti(tmp_db, sessione):
    """Dopo il fix G4: "Edilservice S.p.A." e "Edilservice" sono forme
    diverse → placeholder distinti. Il ripristino torna identico."""
    testo = (
        "Il fornitore Edilservice S.p.A. ha inviato la fattura. "
        "Edilservice conferma la consegna."
    )
    out, ents = anonimizza(
        testo, sessione, db_path=tmp_db,
        categorie_attive={"ORG"},
    )
    org = [e for e in ents if e["tipo"] == "ORG"]
    valori = {e["valore_reale"] for e in org}
    if "Edilservice S.p.A" in valori and "Edilservice" in valori:
        placeholder = {e["placeholder"] for e in org}
        assert len(placeholder) == 2, (
            f"forme diverse → placeholder diversi, invece: {org}"
        )
    rest, _ = deanonimizza(out, sessione, db_path=tmp_db)
    assert rest == testo, (
        f"roundtrip non esatto:\norig: {testo!r}\nrest: {rest!r}"
    )


def test_a2_correlato_a_persona(tmp_db, sessione):
    """Se compaiono "Mario Rossi" e "Rossi", ognuno ha il proprio
    placeholder e ognuno ha ``correlato_a`` che punta all'altro."""
    testo = "Mario Rossi ha firmato. Rossi ha aggiunto una nota."
    _, ents = anonimizza(testo, sessione, db_path=tmp_db)
    per_valore = {e["valore_reale"]: e for e in ents
                  if e.get("tipo") == "PERSONA" and not e.get("suggerito")}
    if "Mario Rossi" in per_valore and "Rossi" in per_valore:
        assert per_valore["Rossi"]["correlato_a"] == per_valore["Mario Rossi"]["placeholder"]
        assert per_valore["Mario Rossi"]["correlato_a"] == per_valore["Rossi"]["placeholder"]


def test_a2_50_entita_distinte_50_placeholder(tmp_db, sessione):
    """50 nomi distinti → 50 placeholder distinti (no fusione errata)."""
    nomi = [f"Persona{i:02d} Cognome{i:02d}" for i in range(50)]
    # Iniettiamo direttamente nel vault via rianonimizza per non dipendere
    # dal riconoscimento neurale su nomi finti.
    from backend.motore import rianonimizza
    testo = "\n".join(f"riga {i}: {n} presente." for i, n in enumerate(nomi))
    ents_input = [{"valore_reale": n, "tipo": "PERSONA"} for n in nomi]
    _out, ents = rianonimizza(testo, sessione, ents_input, db_path=tmp_db)
    placeholders = {e["placeholder"] for e in ents}
    assert len(placeholders) == 50, (
        f"attesi 50 placeholder distinti, trovati {len(placeholders)}"
    )


def test_a2_doppia_anonimizzazione_stessa_sessione_stessa_uscita(tmp_db, sessione):
    """Anonimizzando lo stesso testo due volte nella stessa sessione,
    l'output deve essere identico e non ci devono essere placeholder
    aggiuntivi."""
    testo = (
        "Il cliente Mario Rossi ha firmato il contratto il 19 giugno 2026. "
        "Il pagamento avverrà per il 19/06/2026 come da accordo."
    )
    out1, _ents1 = anonimizza(testo, sessione, db_path=tmp_db,
                              categorie_attive={"PERSONA", "DATA"})
    out2, _ents2 = anonimizza(testo, sessione, db_path=tmp_db,
                              categorie_attive={"PERSONA", "DATA"})
    assert out1 == out2, (
        f"idempotenza rotta:\nprima:  {out1!r}\nseconda: {out2!r}"
    )


# ---------------------------------------------------------------------------
# GRUPPO B1 — Categorie opt-in
# ---------------------------------------------------------------------------

def test_b1_default_esclude_categorie_rumorose():
    """Il default NON include LUOGO/ORG/DATA/IMPORTO/URL/IP/SPEDIZIONE.

    TARGA è passata nel default (2026-07-31, tassonomia PII): il
    recognizer è ora deterministico (formato targhe italiane), non più
    solo neurale — il rischio rumore che l'aveva esclusa è caduto.
    """
    from backend.motore import CATEGORIE_DEFAULT_ATTIVE
    for c in ["LUOGO", "ORG", "DATA", "IMPORTO", "URL", "IP",
              "SPEDIZIONE", "CATASTO", "MAC", "CRYPTO"]:
        assert c not in CATEGORIE_DEFAULT_ATTIVE, (
            f"{c} è rumoroso, non dovrebbe essere attivo per default"
        )
    for c in ["PERSONA", "EMAIL", "TELEFONO", "IBAN", "CF", "PIVA",
              "CARTA", "CAP", "INDIRIZZO", "TARGA", "VIN", "PRATICA",
              "SOCIAL"]:
        assert c in CATEGORIE_DEFAULT_ATTIVE, (
            f"{c} è dato personale, deve essere attivo per default"
        )


def test_b1_categorie_disattive_non_sostituite(tmp_db, sessione):
    """Se DATA è disattiva, una data nel testo non deve essere mascherata."""
    testo = "Riunione del 15 marzo 2026 con Mario Rossi presso via Roma 12, Milano."
    # Categorie default: PERSONA on, DATA/LUOGO off.
    out, _ents = anonimizza(
        testo, sessione, db_path=tmp_db,
        categorie_attive={"PERSONA", "INDIRIZZO"},
    )
    # Persona sostituita.
    assert "Mario Rossi" not in out
    # Data non sostituita (categoria DATA off).
    assert "15 marzo 2026" in out or "marzo 2026" in out
    # Città isolata non sostituita (categoria LUOGO off).
    assert "Milano" in out


def test_b1_categorie_attive_esplicite(tmp_db, sessione):
    """Attivando DATA esplicitamente, la data viene sostituita."""
    testo = "Contratto firmato il 15 marzo 2026 da Mario Rossi."
    out, ents = anonimizza(
        testo, sessione, db_path=tmp_db,
        categorie_attive={"PERSONA", "DATA"},
    )
    assert "Mario Rossi" not in out
    tipi = {e["tipo"] for e in ents}
    # Data deve comparire fra le entità emesse.
    assert "DATA" in tipi, f"attesa DATA fra {tipi}"


def test_b1_persistenza_categorie(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACYBRIDGE_DATA_DIR", str(tmp_path))
    from backend.motore import (
        CATEGORIE_DEFAULT_ATTIVE,
        _leggi_categorie_attive,
        scrivi_categorie_attive,
    )
    # Default se file assente.
    assert _leggi_categorie_attive() == CATEGORIE_DEFAULT_ATTIVE
    # Scrivi e rileggi.
    scrivi_categorie_attive({"PERSONA", "EMAIL"})
    assert _leggi_categorie_attive() == {"PERSONA", "EMAIL"}


# ---------------------------------------------------------------------------
# GRUPPO B2 — Filtri anti-rumore
# ---------------------------------------------------------------------------

def test_b2_tutto_maiuscolo_scartato():
    from backend.filtri_rumore import e_rumore
    for w in ["TECNICO", "APPRESA", "ASSISTENTE", "TITOLO SEZIONE"]:
        assert e_rumore(w), f"{w!r} è tutto maiuscolo, dovrebbe essere rumore"


def test_b2_token_brevi_scartati():
    from backend.filtri_rumore import e_rumore
    for w in ["A", "IT", "OK"]:
        assert e_rumore(w), f"{w!r} è troppo breve"


def test_b2_nomi_file_scartati():
    from backend.filtri_rumore import e_rumore
    for w in ["test.py", "config.json", "README.md", "data/vault.db",
              "models/rizzo.safetensors", "logo.png"]:
        assert e_rumore(w), f"{w!r} è un nome file"


def test_b2_snake_e_camel_scartati():
    from backend.filtri_rumore import e_rumore
    for w in ["get_user_by_id", "my_variable", "APIClient",
              "getUserById", "MyClass"]:
        assert e_rumore(w), f"{w!r} è identificatore di codice"


def test_b2_codici_brevi_scartati():
    from backend.filtri_rumore import e_rumore
    for w in ["P0", "P5-URG", "T1", "A3", "B-12"]:
        assert e_rumore(w), f"{w!r} è codice breve"


def test_b2_lettere_spaziate_scartate():
    from backend.filtri_rumore import e_rumore
    assert e_rumore("C A S E   S T U D Y")
    assert e_rumore("A B C D")


def test_b2_parola_comune_non_nome_scartata():
    from backend.filtri_rumore import e_rumore
    for w in ["Tavolo", "Documento", "Sedia"]:
        assert e_rumore(w), f"{w!r} è parola comune non-nome"


def test_b2_nomi_veri_non_scartati():
    from backend.filtri_rumore import e_rumore
    for w in ["Mario", "Rossi", "Andrea", "Giuseppe", "Ferrari"]:
        assert not e_rumore(w), f"{w!r} è nome legittimo, non deve essere scartato"


# ---------------------------------------------------------------------------
# GRUPPO B3 — Blacklist termini tecnici / marchi pubblici
# ---------------------------------------------------------------------------

def test_b3_marchi_pubblici_scartati():
    from backend.filtri_rumore import e_rumore
    for w in ["Yahoo", "Stripe", "Trade Republic", "Finnhub", "ECB",
              "CoinGecko", "Polygon", "Google", "Microsoft", "Apple",
              "Amazon", "HuggingFace"]:
        assert e_rumore(w), f"{w!r} è marchio pubblico, non dato personale"


def test_b3_metriche_finanziarie_scartate():
    from backend.filtri_rumore import e_rumore
    for w in ["VaR", "CVaR", "NAV", "beta", "drawdown", "Monte Carlo",
              "MSCI", "S&P500", "VIX", "bootstrap"]:
        assert e_rumore(w), f"{w!r} è metrica finanziaria"


def test_b3_tecnologie_scartate():
    from backend.filtri_rumore import e_rumore
    for w in ["SQLite", "WAL", "JSON", "API", "Python", "Telegram",
              "launchd", "macOS", "HTTP", "SQL", "FastAPI"]:
        assert e_rumore(w), f"{w!r} è tecnologia"


def test_b3_e2e_su_frase_tecnica(tmp_db, sessione):
    """Frase piena di rumore tecnico: nessuna sostituzione attesa (0)."""
    testo = (
        "Il modulo backend.motore.py usa SQLite con WAL, espone API REST "
        "via FastAPI, e la query VaR-99 chiama Yahoo Finance con timeout "
        "HTTP di 3s. Il file config.json contiene i parametri."
    )
    out, ents = anonimizza(
        testo, sessione, db_path=tmp_db,
        categorie_attive={"PERSONA", "EMAIL", "TELEFONO", "IBAN", "CF",
                          "PIVA", "CARTA", "CAP", "INDIRIZZO"},
    )
    # Zero sostituzioni attese: non ci sono dati personali.
    assert out == testo, (
        f"attese 0 sostituzioni su frase tecnica, output modificato:\n"
        f"orig: {testo!r}\nout:  {out!r}\nents: {ents}"
    )


# ---------------------------------------------------------------------------
# FASE 4 — Controllo aggiornamenti
# ---------------------------------------------------------------------------

def test_fase4_opt_out_default_attivo(tmp_path, monkeypatch):
    """Default: controllo aggiornamenti attivo."""
    monkeypatch.setenv("PRIVACYBRIDGE_DATA_DIR", str(tmp_path))
    from backend import aggiornamenti
    # Ricarica il modulo se già importato per riprendere il nuovo data dir.
    assert aggiornamenti.check_aggiornamenti_attivo() is True


def test_fase4_persistenza_impostazione(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACYBRIDGE_DATA_DIR", str(tmp_path))
    from backend.aggiornamenti import (
        check_aggiornamenti_attivo,
        imposta_check_aggiornamenti,
    )
    imposta_check_aggiornamenti(False)
    assert check_aggiornamenti_attivo() is False
    imposta_check_aggiornamenti(True)
    assert check_aggiornamenti_attivo() is True
    # Persistenza: file scritto.
    assert (tmp_path / "impostazioni.json").exists()


def test_fase4_confronto_versione():
    from backend.aggiornamenti import _piu_recente
    assert _piu_recente("1.1.0", "1.0.0")
    assert _piu_recente("2.0.0", "1.9.9")
    assert _piu_recente("1.0.1", "1.0.0")
    assert not _piu_recente("1.0.0", "1.0.0")
    assert not _piu_recente("1.0.0", "1.0.1")
    # Formati mal fatti degradano a (0,0,0).
    assert not _piu_recente("boh", "1.0.0")


def test_fase4_thread_non_blocca_quando_disattivato(tmp_path, monkeypatch):
    """Se il controllo è disattivato, il worker non fa alcuna richiesta."""
    monkeypatch.setenv("PRIVACYBRIDGE_DATA_DIR", str(tmp_path))
    from backend.aggiornamenti import (
        controlla_in_background,
        imposta_check_aggiornamenti,
    )
    imposta_check_aggiornamenti(False)

    import socket
    apri_calls = []

    def _no_conn(self, address, *args, **kwargs):
        apri_calls.append(address)
        raise OSError("bloccato dal test")

    monkeypatch.setattr(socket.socket, "connect", _no_conn)
    t = controlla_in_background()
    t.join(timeout=2)
    assert apri_calls == [], f"controllo disattivato ma richieste fatte: {apri_calls}"


def test_fase4_url_configurabile(monkeypatch):
    from backend.aggiornamenti import _url_versione
    monkeypatch.setenv("PRIVACYBRIDGE_URL_VERSIONE", "https://esempio.test/v.json")
    assert _url_versione() == "https://esempio.test/v.json"


def test_avvio_trova_modello_da_launcher_bundle(tmp_path):
    """Regressione del bug 'l'app non si apre': il launcher shell del
    bundle fa ``cd`` alla cartella progetto e lancia ``avvio.py`` da
    lì. In quel contesto ``__file__`` di avvio.py non è dentro un
    ``.app``. Il lookup del modello DEVE trovare il bundle sorella.

    Simula: importa avvio.py, cambia CWD nella cartella progetto,
    chiama ``_trova_modello_nel_pacchetto`` — deve ritornare un
    percorso valido.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    bundle_modello = root / "build" / "PrivacyBridge.app" / "Contents" / "Resources" / "modello"
    if not bundle_modello.is_dir():
        pytest.skip("bundle .app non presente in questo checkout")

    old_cwd = os.getcwd()
    old_env = os.environ.pop("PRIVACYBRIDGE_MODELLO_DIR", None)
    try:
        os.chdir(str(root))
        # Importa avvio con CWD nella cartella progetto (come fa il
        # launcher del bundle).
        import importlib
        import sys
        if "avvio" in sys.modules:
            del sys.modules["avvio"]
        avvio = importlib.import_module("avvio")
        trovato = avvio._trova_modello_nel_pacchetto()
        assert trovato is not None, (
            "Il lookup non ha trovato il modello nel bundle. "
            f"Candidati tentati: {avvio._candidati_percorsi_modello()}"
        )
        assert avvio._valida_modello(trovato), (
            f"Percorso trovato {trovato} non valida"
        )
    finally:
        os.chdir(old_cwd)
        if old_env is not None:
            os.environ["PRIVACYBRIDGE_MODELLO_DIR"] = old_env


def test_avvio_ripiego_cache_hf():
    """Se il bundle manca, il ripiego cache HuggingFace deve
    intervenire.  Testa che ``_trova_modello_hf_cache`` restituisca
    un percorso valido quando la cache è popolata (setup di sviluppo:
    la cache HF è presente perché il modello è stato scaricato in
    passato)."""
    import sys
    if "avvio" in sys.modules:
        del sys.modules["avvio"]
    import importlib
    avvio = importlib.import_module("avvio")
    trovato = avvio._trova_modello_hf_cache()
    # Se qui è None, l'utente non ha mai scaricato il modello — è
    # accettabile: il ripiego non ha nulla da restituire.
    if trovato is not None:
        assert avvio._valida_modello(trovato), (
            f"cache HF trovata a {trovato} ma non valida"
        )


def test_modello_nel_bundle_localizzato():
    """FASE 1.3 — il motore di riconoscimento va localizzato nel
    pacchetto: la cartella ``PrivacyBridge.app/Contents/Resources/modello/``
    deve esistere e contenere i file necessari.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    modello = root / "build" / "PrivacyBridge.app" / "Contents" / "Resources" / "modello"
    assert modello.is_dir(), (
        f"cartella modello mancante nel bundle: {modello}. "
        "Reinstalla o rigenera il pacchetto (vedi FASE 1.3)."
    )
    for atteso in ("config.json", "tokenizer.json", "model.safetensors"):
        assert (modello / atteso).is_file(), (
            f"file atteso {atteso!r} mancante in {modello}"
        )


# ---------------------------------------------------------------------------
# BUG 1 — Deanonimizza tollerante alle decorazioni LLM
# ---------------------------------------------------------------------------
#
# Quando l'utente incolla la risposta di un LLM nel pannello Ripristina,
# i caporali «...» sono spesso persi: virgolette dritte/curve, backtick,
# grassetto markdown, parentesi, ecc.
# La deanonimizzazione DEVE riconoscere il token TIPO_N indipendentemente
# dalla decorazione e consumare anche la decorazione (nessuna virgoletta
# orfana). MAI confondere PERSONA_2 con PERSONA_1.

_DECORAZIONI = [
    # (open, close, descrizione)
    ("«", "»", "caporali canonici"),
    ('"', '"', "virgolette dritte doppie"),
    ("'", "'", "apici dritti"),
    ("“", "”", "virgolette curve doppie"),
    ("‘", "’", "apici curvi"),
    ("[", "]", "parentesi quadre"),
    ("(", ")", "parentesi tonde"),
    ("<", ">", "angolari"),
    ("**", "**", "markdown bold"),
    ("*", "*", "markdown italic"),
    ("__", "__", "markdown bold underscore"),
    ("`", "`", "backtick"),
    ("", "", "nudo, nessuna decorazione"),
]


def test_bug1_singolo_placeholder_ogni_decorazione(tmp_db, sessione):
    """Un solo placeholder, provato con ogni decorazione."""
    testo = "Il cliente Mario Rossi ha firmato."
    anon, _ = anonimizza(testo, sessione, db_path=tmp_db)
    assert "«PERSONA_1»" in anon

    body = "PERSONA_1"
    for open_, close_, descr in _DECORAZIONI:
        risposta = f"Ecco la risposta: {open_}{body}{close_} ha confermato."
        restored, _report = deanonimizza(risposta, sessione, db_path=tmp_db)
        assert "Mario Rossi" in restored, (
            f"decorazione {descr!r}: nome non ripristinato in {restored!r}"
        )
        # La decorazione non deve restare orfana attorno al valore reale.
        # (Nel testo circostante "Ecco la risposta:" nessun problema).
        if open_ and open_ != close_:
            assert open_ + "Mario Rossi" not in restored, (
                f"decorazione {descr!r}: apertura {open_!r} lasciata orfana"
            )
            assert "Mario Rossi" + close_ not in restored, (
                f"decorazione {descr!r}: chiusura {close_!r} lasciata orfana"
            )


def test_bug1_20_placeholder_decorazioni_miste(tmp_db, sessione):
    """20 placeholder distinti, decorazioni mescolate: nessuna confusione.

    Non passiamo per l'anonimizzatore neurale (che non riconoscerebbe
    nomi finti): iniettiamo direttamente 20 entità nel vault e testiamo
    la sola deanonimizzazione, che è ciò che il BUG 1 riguarda.
    """
    from backend.vault import Vault
    v = Vault(tmp_db)
    try:
        for i in range(20):
            v.add(
                sessione,
                f"«PERSONA_{i + 1}»",
                f"NomeUnico{i:02d} CognomeUnico{i:02d}",
                "PERSONA",
            )
    finally:
        v.close()

    import random
    random.seed(42)
    frasi = []
    valori_attesi = []
    for i in range(20):
        ph_body = f"PERSONA_{i + 1}"
        val = f"NomeUnico{i:02d} CognomeUnico{i:02d}"
        valori_attesi.append(val)
        open_, close_, _ = random.choice(_DECORAZIONI)
        frasi.append(f"Riga {i}: quanto a {open_}{ph_body}{close_}, la valutazione è ok.")
    risposta = "\n".join(frasi)

    restored, _report = deanonimizza(risposta, sessione, db_path=tmp_db)

    # Ogni valore reale deve comparire ESATTAMENTE una volta.
    for val in valori_attesi:
        assert restored.count(val) == 1, (
            f"valore {val!r} appare {restored.count(val)} volte in output: "
            "confusione fra placeholder"
        )

    # Verifica di ordine posizionale: PERSONA_1 ha ricevuto NomeUnico00,
    # PERSONA_2 ha ricevuto NomeUnico01, ecc. Le frasi sono su righe
    # separate — la riga i-esima deve contenere il valore i-esimo.
    for i, riga in enumerate(restored.split("\n")):
        val_atteso = f"NomeUnico{i:02d} CognomeUnico{i:02d}"
        assert val_atteso in riga, (
            f"riga {i} contiene {riga!r}, atteso {val_atteso!r}: "
            "possibile scambio fra placeholder"
        )


def test_bug1_placeholder_con_spazio_spurio(tmp_db, sessione):
    """PERSONA _2 con spazio spurio prima dell'underscore deve funzionare."""
    testo = "Il cliente Mario Rossi ha firmato."
    _anon, _ = anonimizza(testo, sessione, db_path=tmp_db)

    risposta = "Il testo dice: PERSONA _1 ha confermato."
    restored, _ = deanonimizza(risposta, sessione, db_path=tmp_db)
    assert "Mario Rossi" in restored, f"spazio spurio non gestito: {restored!r}"


def test_bug1_placeholder_case_insensitive(tmp_db, sessione):
    """persona_1 (minuscolo) deve funzionare come PERSONA_1."""
    testo = "Il cliente Mario Rossi ha firmato."
    _anon, _ = anonimizza(testo, sessione, db_path=tmp_db)

    risposta = "Il testo dice: persona_1 ha confermato."
    restored, _ = deanonimizza(risposta, sessione, db_path=tmp_db)
    assert "Mario Rossi" in restored


def test_bug1_no_confusione_ph_adiacenti(tmp_db, sessione):
    """Due placeholder adiacenti non devono contaminarsi."""
    testo = "Mario Rossi e Luigi Bianchi hanno firmato insieme."
    _anon, _ = anonimizza(testo, sessione, db_path=tmp_db)

    risposta = "Ecco: \"PERSONA_1\" e \"PERSONA_2\" — grazie."
    restored, _ = deanonimizza(risposta, sessione, db_path=tmp_db)
    assert "Mario Rossi" in restored
    assert "Luigi Bianchi" in restored
    # Mario e Luigi devono comparire una sola volta ciascuno.
    assert restored.count("Mario Rossi") == 1
    assert restored.count("Luigi Bianchi") == 1


def test_bug1_ph_dentro_lista_markdown(tmp_db, sessione):
    """Risposta LLM tipica: elenco puntato con placeholder."""
    testo = "Contatti: Mario Rossi, Luigi Bianchi, Anna Verdi."
    _anon, _ = anonimizza(testo, sessione, db_path=tmp_db)

    risposta = (
        "Elenco dei nominativi menzionati:\n"
        "- **PERSONA_1**\n"
        "- **PERSONA_2**\n"
        "- **PERSONA_3**\n"
    )
    restored, _ = deanonimizza(risposta, sessione, db_path=tmp_db)
    for atteso in ["Mario Rossi", "Luigi Bianchi", "Anna Verdi"]:
        assert atteso in restored
        # I doppi asterischi non devono restare attorno al valore.
        assert f"**{atteso}**" not in restored, (
            f"asterischi orfani attorno a {atteso}"
        )


def test_bug1_ph_sconosciuto_lasciato_invariato(tmp_db, sessione):
    """Un TIPO_N sconosciuto (non nel vault) resta invariato + warning."""
    testo = "Mario Rossi ha firmato."
    _anon, _ = anonimizza(testo, sessione, db_path=tmp_db)

    # PERSONA_99 non esiste nel vault
    risposta = "Ok, «PERSONA_1» e \"PERSONA_99\" firmano."
    restored, report = deanonimizza(risposta, sessione, db_path=tmp_db)
    assert "Mario Rossi" in restored
    # PERSONA_99 wrapped tra virgolette dritte: resta invariato compresa la decorazione
    assert "PERSONA_99" in restored
    assert "«PERSONA_99»" in report["warning"]


def test_bug1_testo_normale_con_pattern_simile(tmp_db, sessione):
    """Parole normali che assomigliano a TIPO_N non devono essere sostituite."""
    testo = "Mario Rossi ha firmato."
    _anon, _ = anonimizza(testo, sessione, db_path=tmp_db)

    # "test_1" contiene un underscore + numero ma non è un placeholder noto:
    # deve essere lasciato invariato.
    risposta = "Vedi il file test_1 e version_2 del report."
    restored, _report = deanonimizza(risposta, sessione, db_path=tmp_db)
    assert "test_1" in restored
    assert "version_2" in restored


# ---------------------------------------------------------------------------
# FASE 2 — Dizionario nomi italiani (3 livelli) + rubrica
# ---------------------------------------------------------------------------

def _persone(ents):
    return [e for e in ents if "PERSONA" in e["tipo"] and not e.get("suggerito")]

def _suggeriti(ents):
    return [e for e in ents if e.get("suggerito")]


def test_faseg_ciao_sono_andrea(tmp_db, sessione):
    """Il caso canonico del briefing: nome di battesimo colloquiale
    isolato in una frase informale. DEVE essere riconosciuto e
    sostituito."""
    testo = "Ciao sono Andrea, ti scrivo per il preventivo di via Roma 12."
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Andrea" not in out, (
        f"Il nome 'Andrea' non è stato sostituito. Output: {out!r}. "
        f"Entità: {ents}"
    )
    persone = _persone(ents)
    assert any(p["valore_reale"] == "Andrea" for p in persone), (
        f"Nessuna entità PERSONA per 'Andrea'. Persone: {persone}"
    )


def test_faseg_nome_ambiguo_con_contesto_forte_attivo(tmp_db, sessione):
    """'sono Rosa' è contesto forte: Rosa (ambigua) diventa PERSONA attivo."""
    testo = "Sono Rosa dell'amministrazione, chiedo aggiornamento."
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Rosa" not in out, f"'Rosa' non sostituita. Output: {out!r}"


def test_faseg_nome_ambiguo_senza_contesto_solo_suggerito(tmp_db, sessione):
    """'colore rosa' minuscolo: parola comune, mai emessa."""
    testo = "Il tessuto è di colore rosa acceso."
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert out == testo, (
        f"Nessuna sostituzione attesa, output modificato: {out!r}"
    )


def test_faseg_nome_ambiguo_inizio_frase_declassato(tmp_db, sessione):
    """Nome che coincide con parola comune ("Vittoria", "Fiore",
    "Bruno") a INIZIO FRASE + seguito da sostantivo/aggettivo NON è
    livello 1: viene declassato a suggerimento perché in italiano
    l'inizio-frase forza la maiuscola su qualunque parola.
    """
    for testo in [
        "Vittoria schiacciante per la squadra ospite.",
        "Fiore all'occhiello del catalogo primaverile.",
    ]:
        out, _ents = anonimizza(testo, sessione + "-" + testo[:3], db_path=tmp_db)
        # Il nome NON deve essere sostituito (falsi positivi in inizio-frase).
        primo = testo.split()[0]
        assert primo in out, (
            f"'{primo}' non doveva essere sostituito in inizio-frase "
            f"con parola comune. Output: {out!r}"
        )


def test_faseg_formula_apertura_non_diventa_nome(tmp_db, sessione):
    """'Gentile' è un cognome vero ma anche una formula di apertura:
    non deve essere emesso come nome/suggerimento nemmeno a livello 3."""
    testo = "Gentile Signor Rossi, la informiamo che il colloquio è confermato."
    _out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    for e in ents:
        assert e["valore_reale"] != "Gentile", (
            f"'Gentile' emesso come entità: {e}"
        )


def test_faseg_parola_comune_inizio_frase_non_suggerita(tmp_db, sessione):
    """Parola comune con la maiuscola d'inizio frase: nessun suggerimento.

    Le frasi vengono dai documenti reali dell'utente. "Che", "Alla",
    "Durante" sono tutte in ``cognomi_italiani.tsv``: senza il controllo
    sul vocabolario il riquadro "Possibili entità" le proponeva come
    persone, e ne mostra cinque per volta.
    """
    for testo in [
        "Che tipo di dati personali vengono elaborati?",
        ("Alla luce di quanto sopra, si ritiene di aver acquisito ulteriori "
         "elementi."),
        "Durante l'intero processo di lavorazione nessuno potra sapere chi sei.",
    ]:
        out, ents = anonimizza(testo, sessione + "-" + testo[:4], db_path=tmp_db)
        assert out == testo, f"testo modificato: {out!r}"
        assert not _suggeriti(ents), (
            f"suggerimenti su parole comuni: "
            f"{[e['valore_reale'] for e in _suggeriti(ents)]} — {testo!r}"
        )


def test_faseg_testo_minuscolo_non_genera_suggerimenti(tmp_db, sessione):
    """Su testo tutto minuscolo il truecasing non deve inventare persone.

    La ricapitalizzazione mette la maiuscola a ogni parola per far
    emergere i nomi scritti in minuscolo; di conseguenza ogni parola
    diventa candidata. Una maiuscola messa da noi non è una prova.
    """
    testo = (
        "in riferimento al procedimento penale, si comunica che i dati sono "
        "stati acquisiti dal tuo gestore in data odierna."
    )
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert out == testo, f"testo modificato: {out!r}"
    assert not _suggeriti(ents), (
        f"suggerimenti da truecasing: "
        f"{[e['valore_reale'] for e in _suggeriti(ents)]}"
    )


def test_faseg_cognome_vero_senza_contesto_resta_suggerito(tmp_db, sessione):
    """Controcaso: il filtro non deve svuotare il riquadro.

    "Bertini" non è una parola italiana, quindi la presenza in lista
    cognomi è un indizio vero. Senza contesto personale resta un
    suggerimento — proposto, non sostituito."""
    testo = "Il documento e stato firmato da Bertini in data odierna."
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Bertini" in out, f"'Bertini' sostituito senza contesto: {out!r}"
    assert [e["valore_reale"] for e in _suggeriti(ents)] == ["Bertini"], (
        f"'Bertini' non proposto. Suggeriti: "
        f"{[e['valore_reale'] for e in _suggeriti(ents)]}"
    )


def test_faseg_nome_dopo_titolo_attivo(tmp_db, sessione):
    """'signor Rocco' → titolo + nome, contesto forte per livello 2."""
    testo = "Ha chiamato il signor Rocco per confermare la riunione."
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Rocco" not in out, f"'Rocco' non sostituito. Output: {out!r}"


def test_faseg_nome_in_apertura_email(tmp_db, sessione):
    """'Ciao Andrea,' a inizio riga: apertura → livello 2."""
    testo = "Ciao Andrea,\nti giro il documento come chiesto.\nGrazie."
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Andrea" not in out, f"'Andrea' non sostituito. Output: {out!r}"


def test_faseg_firma_finale_con_saluti(tmp_db, sessione):
    """Firma finale dopo 'Cordiali saluti,' → livello 2 anche per nomi
    ambigui."""
    testo = (
        "Buongiorno,\n"
        "ecco il documento che mi aveva richiesto.\n"
        "Cordiali saluti,\n"
        "Grazia"
    )
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    # 'Grazia' è nome ambiguo; nella firma finale con 'Cordiali saluti'
    # è livello 2 → deve essere sostituita.
    assert "Grazia" not in out.split("\n")[-1], (
        f"'Grazia' nella firma finale non sostituita. Output: {out!r}"
    )


def test_faseg_nome_cognome_adiacenti(tmp_db, sessione):
    """Nome + cognome adiacenti, entrambi noti: sostituzione unica."""
    testo = "Passa a trovare Giulia Ferrari domani in ufficio."
    out, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "Giulia Ferrari" not in out, (
        f"'Giulia Ferrari' non sostituito. Output: {out!r}"
    )


def test_faseg_nomi_frequenti_carichi_dal_dizionario():
    """Sanity check: nomi comuni sono nel dizionario."""
    from backend.nomi_italiani import _COGN_TUTTI, _NOMI_TUTTI
    assert len(_NOMI_TUTTI) >= 5000, f"nomi caricati: {len(_NOMI_TUTTI)}"
    assert len(_COGN_TUTTI) >= 20000, f"cognomi caricati: {len(_COGN_TUTTI)}"
    for n in ["andrea", "mario", "luigi", "giuseppe", "anna", "francesco"]:
        assert n in _NOMI_TUTTI, f"nome comune {n!r} mancante nel dizionario"
    for c in ["rossi", "bianchi", "ferrari", "russo", "colombo"]:
        assert c in _COGN_TUTTI, f"cognome comune {c!r} mancante nel dizionario"


# ---------------------------------------------------------------------------
# FASE 2.3 — Rubrica personale
# ---------------------------------------------------------------------------

def test_rubrica_add_e_get(tmp_db):
    """Aggiunta/rimozione/lettura basiche."""
    v = Vault(tmp_db)
    try:
        v.rubrica_add("ACME Srl", "ORG")
        v.rubrica_add("Cliente Zeta", "PERSONA")
        v.rubrica_add("ACME Srl", "ORG")  # duplicato: idempotente
        righe = list(v.rubrica_all())
        assert len(righe) == 2
        testi = {r["testo"] for r in righe}
        assert testi == {"ACME Srl", "Cliente Zeta"}
        v.rubrica_remove("Cliente Zeta")
        assert v.rubrica_count() == 1
    finally:
        v.close()


def test_rubrica_recognizer_sostituisce(tmp_db, sessione, monkeypatch):
    """Termine in rubrica: sostituito sempre, anche se il neurale
    non l'avrebbe visto."""
    v = Vault(tmp_db)
    try:
        v.rubrica_add("CodiceProdotto42", "ALTRO")
        v.rubrica_add("Cliente Zeta", "PERSONA")
    finally:
        v.close()

    from backend.motore import anonimizza, reset_analyzer

    # Forzo l'analyzer a usare il tmp_db per la rubrica.
    monkeypatch.setenv("PRIVACYBRIDGE_DB", tmp_db)
    reset_analyzer()
    try:
        testo = "Ordine per Cliente Zeta del prodotto CodiceProdotto42."
        out, ents = anonimizza(testo, sessione, db_path=tmp_db)
        assert "CodiceProdotto42" not in out
        assert "Cliente Zeta" not in out
        tipi = {(e["valore_reale"], e["tipo"]) for e in ents}
        assert ("CodiceProdotto42", "ALTRO") in tipi
        assert ("Cliente Zeta", "PERSONA") in tipi
    finally:
        # Reset globale per evitare che altre suite ereditino la rubrica.
        monkeypatch.undo()
        reset_analyzer()


def test_carica_modello_da_percorso_locale(monkeypatch, tmp_path):
    """FASE 1.3 — quando ``PRIVACYBRIDGE_MODELLO_DIR`` punta a una
    cartella valida, il recognizer deve caricarsi da lì senza contattare
    l'esterno.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    modello = root / "build" / "PrivacyBridge.app" / "Contents" / "Resources" / "modello"
    if not modello.is_dir():
        pytest.skip("modello nel bundle non presente in questo checkout")

    monkeypatch.setenv("PRIVACYBRIDGE_MODELLO_DIR", str(modello))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    from backend.motore_neurale import _percorso_modello_locale, build_neural_recognizer
    assert _percorso_modello_locale() == str(modello)

    reco = build_neural_recognizer()
    assert reco is not None, "recognizer non caricato dal bundle locale"


# ---------------------------------------------------------------------------
# 13. FIX 1: span completi per IBAN / CF / P.IVA (no prefix-only match)
# ---------------------------------------------------------------------------

def _iban_intl_check(bban: str, cc: str) -> str:
    numeric = ""
    for ch in bban + cc + "00":
        numeric += ch if ch.isdigit() else str(ord(ch) - 55)
    check = 98 - (int(numeric) % 97)
    return f"{check:02d}"


def _make_iban_intl(bban: str, cc: str = "IT") -> str:
    return f"{cc}{_iban_intl_check(bban, cc)}{bban}"


def _analyze_and_get_spans(testo: str, entity_type: str):
    """Restituisce gli span (start, end, text) del tipo richiesto trovati
    dall'analyzer, senza passare per il vault. Utile per FIX 1.
    """
    analyzer = get_analyzer()
    results = analyzer.analyze(text=testo, language="it")
    return [
        (r.start, r.end, testo[r.start:r.end])
        for r in results
        if r.entity_type == entity_type
    ]


def _span_copre_tutto(spans, target: str, testo: str) -> bool:
    """True se almeno uno span coincide con ``target`` nel testo."""
    return any(testo[s:e] == target for s, e, _ in spans)


def test_fix1_iban_attaccato(tmp_db, sessione):
    iban = _make_iban_intl("X0542811101000000123456")
    testo = f"IBAN {iban} fine."
    spans = _analyze_and_get_spans(testo, "IT_IBAN")
    assert _span_copre_tutto(spans, iban, testo), \
        f"IBAN attaccato non catturato interamente. spans={spans}"


def test_fix1_iban_con_spazi(tmp_db, sessione):
    iban = _make_iban_intl("X0542811101000000123456")
    iban_spaced = " ".join([iban[i:i+4] for i in range(0, len(iban), 4)])
    testo = f"IBAN: {iban_spaced} — grazie"
    spans = _analyze_and_get_spans(testo, "IT_IBAN")
    assert _span_copre_tutto(spans, iban_spaced, testo), \
        f"IBAN con spazi non catturato interamente. spans={spans}"


def test_fix1_iban_estero_de(tmp_db, sessione):
    iban = "DE89370400440532013000"
    testo = f"Bonifico su IBAN {iban} per Alice."
    spans = _analyze_and_get_spans(testo, "IT_IBAN")
    assert _span_copre_tutto(spans, iban, testo), \
        f"IBAN estero (DE) non catturato. spans={spans}"


def test_fix1_iban_estero_fr(tmp_db, sessione):
    iban = "FR7630006000011234567890189"
    testo = f"IBAN {iban}."
    spans = _analyze_and_get_spans(testo, "IT_IBAN")
    assert _span_copre_tutto(spans, iban, testo), \
        f"IBAN estero (FR) non catturato. spans={spans}"


def test_fix1_iban_minuscolo(tmp_db, sessione):
    iban = _make_iban_intl("X0542811101000000123456")
    iban_lc = iban.lower()
    testo = f"L'iban è {iban_lc}."
    spans = _analyze_and_get_spans(testo, "IT_IBAN")
    assert _span_copre_tutto(spans, iban_lc, testo), \
        f"IBAN minuscolo non catturato. spans={spans}"


def test_fix1_cf_span_16_esatti(tmp_db, sessione):
    cf = "RSSMRA80A01H501U"
    testo = f"CF: {cf}."
    spans = _analyze_and_get_spans(testo, "IT_CODICE_FISCALE")
    assert _span_copre_tutto(spans, cf, testo), \
        f"CF non catturato interamente. spans={spans}"
    # Ogni span di CF deve essere ESATTAMENTE di 16 caratteri.
    for s, e, t in spans:
        assert e - s == 16, f"span CF di lunghezza {e-s}: {t!r}"


def test_fix1_cf_minuscolo(tmp_db, sessione):
    cf = "rssmra80a01h501u"
    testo = f"cf {cf} qui"
    spans = _analyze_and_get_spans(testo, "IT_CODICE_FISCALE")
    assert _span_copre_tutto(spans, cf, testo), \
        f"CF minuscolo non catturato. spans={spans}"


def test_fix1_piva_attaccata(tmp_db, sessione):
    piva = "12345678903"
    testo = f"P.IVA {piva}"
    spans = _analyze_and_get_spans(testo, "IT_PARTITA_IVA")
    assert _span_copre_tutto(spans, piva, testo), \
        f"P.IVA attaccata non catturata. spans={spans}"


def test_fix1_piva_con_spazi(tmp_db, sessione):
    # 12345678903 con formattazione 5+5+1
    piva_spaced = "12345 67890 3"
    testo = f"Partita IVA: {piva_spaced}."
    spans = _analyze_and_get_spans(testo, "IT_PARTITA_IVA")
    assert _span_copre_tutto(spans, piva_spaced, testo), \
        f"P.IVA con spazi non catturata. spans={spans}"


def test_fix1_no_leakage_iban_completo(tmp_db, sessione):
    """Regressione end-to-end: l'IBAN completo non deve MAI restare in
    output. Testa il vero flusso ``anonimizza``.
    """
    iban = _make_iban_intl("X0542811101000000123456")
    iban_spaced = " ".join([iban[i:i+4] for i in range(0, len(iban), 4)])
    testo = f"Il mio conto è IBAN {iban_spaced} per il bonifico."
    anon, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    # Nessuna sequenza di 5+ cifre consecutive dell'IBAN deve sopravvivere.
    for i in range(len(iban) - 4):
        chunk = iban[i:i+5]
        assert chunk not in anon, (
            f"Frammento IBAN {chunk!r} presente nel testo anonimizzato:\n{anon}"
        )


# ---------------------------------------------------------------------------
# 15. FASE F — Nuovi test end-to-end per IBAN / CF / P.IVA (post-fix)
#     Verificano che il flusso completo ``anonimizza`` mascheri il valore,
#     indipendentemente dal tipo esatto assegnato (che può variare per
#     ambiguità naturale di alcune sequenze di cifre).
# ---------------------------------------------------------------------------

def _valore_non_presente(anon: str, valore: str) -> None:
    assert valore not in anon, (
        f"Valore {valore!r} presente nel testo anonimizzato:\n{anon}"
    )


def test_fasef_iban_con_spazi_end_to_end(tmp_db, sessione):
    """IBAN con spazi ogni 4 caratteri: no leak nel flusso completo."""
    iban = _make_iban_intl("X0542811101000000123456")
    iban_spaced = " ".join(iban[i:i+4] for i in range(0, len(iban), 4))
    testo = f"Effettui il bonifico su IBAN {iban_spaced} entro venerdì."
    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)
    _valore_non_presente(anon, iban_spaced)
    # Deve emettere un placeholder IBAN.
    assert any(e["tipo"] == "IBAN" for e in ents), (
        f"nessun placeholder IBAN emesso. entita={ents}"
    )


def test_fasef_iban_estero_end_to_end(tmp_db, sessione):
    """IBAN estero (DE): no leak."""
    iban = "DE89370400440532013000"
    testo = f"Il fornitore chiede pagamento su IBAN {iban} per la fattura."
    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)
    _valore_non_presente(anon, iban)
    assert any(e["tipo"] == "IBAN" for e in ents), (
        f"nessun placeholder IBAN emesso. entita={ents}"
    )


def test_fasef_iban_minuscolo_misto_end_to_end(tmp_db, sessione):
    """IBAN con case misto (lowercase countries + uppercase digits): no leak."""
    iban = _make_iban_intl("X0542811101000000123456")
    iban_mixed = iban[:2].lower() + iban[2:]
    testo = f"L'iban di riferimento è {iban_mixed}. Grazie."
    anon, _ents = anonimizza(testo, sessione, db_path=tmp_db)
    _valore_non_presente(anon, iban_mixed)


def test_fasef_cf_persona_fisica_16(tmp_db, sessione):
    """CF persona fisica 16 char: no leak, span esatto."""
    cf = "RSSMRA80A01H501U"
    testo = f"Il codice fiscale del cliente è {cf} come da anagrafica."
    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)
    _valore_non_presente(anon, cf)
    assert any(e["tipo"] == "CF" for e in ents), (
        f"nessun placeholder CF emesso. entita={ents}"
    )


def test_fasef_cf_ente_11_cifre(tmp_db, sessione):
    """CF ente/condominio 11 cifre con parola chiave contestuale: no leak."""
    cf_ente = "80012330584"
    testo = (
        f"Il codice fiscale del condominio è {cf_ente} come da statuto. "
        "Contattare l'amministratore."
    )
    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)
    _valore_non_presente(anon, cf_ente)
    # Deve essere un CF (non un altro tipo casuale).
    assert any(e["tipo"] == "CF" and e["valore_reale"] == cf_ente for e in ents), (
        f"CF ente 11 cifre non catalogato correttamente. entita={ents}"
    )


def test_fasef_piva_11_cifre(tmp_db, sessione):
    """P.IVA 11 cifre valida: no leak.

    Nota: 11 cifre in italiano sono ambigue tra P.IVA, CF ente, telefono.
    Il vincolo cardinale è "non lasciare il valore in chiaro"; il tipo
    esatto è secondario (l'utente lo corregge in UI se serve).
    """
    piva = "12345678903"
    testo = f"Fatturato dalla ditta con P.IVA {piva} nel bilancio 2024."
    anon, ents = anonimizza(testo, sessione, db_path=tmp_db)
    _valore_non_presente(anon, piva)
    # Deve essere emesso almeno un placeholder che copre il valore.
    assert ents, f"nessuna entità rilevata sul testo con P.IVA: {testo!r}"


# ---------------------------------------------------------------------------
# FASE 7 — Nomi ambigui residui (Gate 1)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("testo,nome_atteso", [
    ("Ci vediamo domani da Marco alle otto.", "Marco"),
    ("scrivi a luca lo bianco per il preventivo", "luca lo bianco"),
    ("l'ing. Bianco ha firmato il progetto", "Bianco"),
    ("sono passato da Grazia stamattina", "Grazia"),
])
def test_gate1_nomi_ambigui_residui(tmp_db, testo, nome_atteso):
    """Gate 1 (fase nomi ambigui): i 4 casi documentati devono essere
    tutti mascherati.

    - "Marco" e "Grazia": nomi del seed top ISTAT, non-ambigui dopo la
      rigenerazione del TSV → sostituzione garantita anche quando il
      neurale emette LOCATION su "da X" (fix in _scarta_luogo_su_nome_certo).
    - "l'ing. Bianco": cognome ambiguo con titolo forte "ing." → livello 2.
    - "luca lo bianco": particella "lo" ammessa dopo nome minuscolo con
      contesto forte "a luca" → cognome composto.
    """
    sess = "gate1-" + uuid.uuid4().hex[:6]
    anon, ents = anonimizza(testo, sess, db_path=tmp_db)
    _valore_non_presente(anon, nome_atteso)
    assert any(
        e.get("tipo") == "PERSONA" and not e.get("suggerito")
        for e in ents
    ), f"nessuna PERSONA (non-suggerita) rilevata in {testo!r}. ents={ents}"


def test_gate1_inizio_frase_uso_comune_non_declassato_a_persona(tmp_db):
    """Regressione: nomi del seed che coincidono con parole comuni
    ("Vittoria schiacciante", "Fiore all'occhiello") a inizio frase
    seguiti da parola comune restano NON sostituiti."""
    for testo in [
        "Vittoria schiacciante per la squadra ospite.",
        "Fiore all'occhiello del catalogo primaverile.",
    ]:
        sess = "gate1i-" + uuid.uuid4().hex[:6]
        anon, _ = anonimizza(testo, sess, db_path=tmp_db)
        primo = testo.split()[0]
        assert primo in anon, (
            f"'{primo}' non doveva essere sostituito. Output: {anon!r}"
        )
