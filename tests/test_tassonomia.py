# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Test dei recognizer deterministici della tassonomia PII (PARTE 1).

Ogni recognizer nuovo ha tre gruppi di casi: VALIDI (devono essere
riconosciuti), NON VALIDI (non devono), AL LIMITE (comportamento
documentato). I test unitari chiamano ``analyze`` direttamente sul
recognizer (veloci, nessun modello); i test end-to-end passano da
``anonimizza`` e verificano categoria di default e placeholder.
"""

from __future__ import annotations

import uuid

import pytest

from backend.recognizers import (
    CatastoRecognizer,
    DocumentoIdentitaRecognizer,
    IndirizzoItalianoRecognizer,
    PraticaRecognizer,
    SocialHandleRecognizer,
    TargaItalianaRecognizer,
    VINRecognizer,
)


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "vault.db")


@pytest.fixture
def sessione():
    return str(uuid.uuid4())


def _spans(rec, testo, soglia=0.4):
    return [
        testo[r.start:r.end]
        for r in rec.analyze(testo, entities=[])
        if r.score >= soglia
    ]


# ---------------------------------------------------------------------------
# TARGA
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("testo,atteso", [
    # VALIDI — formato auto moderno, anche senza keyword
    ("prendiamo un auto targata FG771XD", "FG771XD"),
    ("il veicolo FG 771 XD era parcheggiato", "FG 771 XD"),
    ("targa FG-771-XD rilevata", "FG-771-XD"),
    ("l'auto ab123cd del vicino", "ab123cd"),                # minuscolo
    # VALIDI — moto/storica solo con keyword
    ("moto con targa BA12345 sequestrata", "BA12345"),
    ("veicolo storico targato MI 123456", "MI 123456"),
])
def test_targa_valide(testo, atteso):
    assert atteso in _spans(TargaItalianaRecognizer(), testo)


@pytest.mark.parametrize("testo", [
    # NON VALIDI
    "il modello AI123BC non esiste",        # I non ammessa nell'alfabeto targhe
    "codice QO123UD respinto",              # Q/O/U non ammesse
    "BA12345 senza contesto veicolare",     # moto senza keyword
    "MI 123456 fattura di dicembre",        # storica senza keyword
    "versione 2.771 del software",
])
def test_targa_non_valide(testo):
    assert _spans(TargaItalianaRecognizer(), testo) == []


def test_targa_limite_dentro_codice_lungo():
    # AL LIMITE: la sequenza è parte di un codice più lungo → no match.
    assert _spans(TargaItalianaRecognizer(), "codice XFG771XD9 interno") == []


@pytest.mark.parametrize("testo", [
    # Classe FP reale (doc tecnico): "sigla numero unità" in elenchi file.
    "report_engine.py 199 KB aggiornato",
    "backup.py 150 KB su disco",
    "consumo di 12 kw ora",
    "lo schermo da 15 PX 400 HZ",
])
def test_targa_non_confonde_file_e_unita(testo):
    assert _spans(TargaItalianaRecognizer(), testo) == []


def test_targa_spaziata_richiede_maiuscole():
    # La forma con spazi in case misto è quasi sempre rumore tecnico.
    assert _spans(TargaItalianaRecognizer(), "vedi fg 771 Xd nel log") == []
    # Ma la keyword veicolare + maiuscole resta valida anche con unità.
    assert "AB 123 CV" in _spans(
        TargaItalianaRecognizer(), "auto con targa AB 123 CV sequestrata"
    )


# ---------------------------------------------------------------------------
# VIN
# ---------------------------------------------------------------------------

def test_vin_valido_con_keyword():
    testo = "numero di telaio ZFA1234567B123456 del veicolo"
    assert "ZFA1234567B123456" in _spans(VINRecognizer(), testo)


def test_vin_valido_keyword_vin():
    testo = "VIN: WVWZZZ1JZ3W386752"
    assert "WVWZZZ1JZ3W386752" in _spans(VINRecognizer(), testo)


@pytest.mark.parametrize("testo", [
    "ZFA1234567B123456 senza alcun contesto",     # niente keyword
    "telaio ABCDEFGHJKLMNPRSZ in acciaio",        # 17 lettere senza cifre
    "telaio ZFA1234567B12345 corto",              # 16 caratteri
    "telaio ZFA1234567I123456 con I",             # lettera I vietata
])
def test_vin_non_validi(testo):
    assert _spans(VINRecognizer(), testo) == []


# ---------------------------------------------------------------------------
# CATASTO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("testo,atteso", [
    ("immobile al foglio 12 particella 345 sub 6 del NCEU",
     "foglio 12 particella 345 sub 6"),
    ("censito al fg. 8 part. 120", "fg. 8 part. 120"),
    ("Foglio 45, mappale 678, subalterno 9", "Foglio 45, mappale 678, subalterno 9"),
])
def test_catasto_validi(testo, atteso):
    assert atteso in _spans(CatastoRecognizer(), testo)


@pytest.mark.parametrize("testo", [
    "il foglio 12 della relazione",       # "foglio" senza particella
    "un foglio di carta",
])
def test_catasto_non_validi(testo):
    assert _spans(CatastoRecognizer(), testo) == []


# ---------------------------------------------------------------------------
# PRATICA (RG, sentenza, protocollo, fattura, polizza, matricola…)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("testo,atteso", [
    ("procedimento R.G. 1234/2023 presso il Tribunale", "1234/2023"),
    ("RG n. 567/22", "567/22"),
    ("sentenza n. 89/2021 della Corte", "89/2021"),
    ("prot. n. 45210 del Comune", "45210"),
    ("protocollo 2024/00123", "2024/00123"),
    ("pratica n. AB-2024-77", "AB-2024-77"),
    ("atto rep. 12345 racc. 6789", "12345"),
    ("fattura n. 2024/151 intestata al cliente", "2024/151"),
    ("polizza n. 998877-K", "998877-K"),
    ("matricola INPS 1234567890", "1234567890"),
    ("posizione INAIL n. 87654321", "87654321"),
    ("iscrizione albo n. A12345", "A12345"),
    ("verbale n. 12/2024 della polizia municipale", "12/2024"),
    ("codice identificativo contratto T4H88KLM2P", "T4H88KLM2P"),
])
def test_pratica_validi(testo, atteso):
    assert atteso in _spans(PraticaRecognizer(), testo)


@pytest.mark.parametrize("testo", [
    "il protocollo HTTPS è cifrato",        # id senza cifre
    "la pratica sportiva fa bene",          # nessun numero
    "fattura elettronica obbligatoria",     # nessun numero
    "la sentenza è stata dura",
    # Classe FP reale (report tecnico): "RG" dentro "ORG" — il confine
    # alfabetico deve bloccare il match dentro parole più lunghe.
    "ORG 194,863 TARGA 19,716",
    "op .983 ORG 145 .967 1.00",
])
def test_pratica_non_validi(testo):
    assert _spans(PraticaRecognizer(), testo) == []


def test_pratica_non_cattura_punto_finale():
    # Classe FP reale: il punto di fine frase non fa parte dell'id.
    spans = _spans(PraticaRecognizer(), "aperta la pratica n. 1234/2024.")
    assert spans == ["1234/2024"]


# ---------------------------------------------------------------------------
# SOCIAL (@handle)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("testo,atteso", [
    ("seguimi su instagram @mario.rossi_88", "@mario.rossi_88"),
    ("il profilo @andreasforna pubblica poco", "@andreasforna"),
    ("scrivimi su telegram @ma_ri", "@ma_ri"),
])
def test_social_validi(testo, atteso):
    assert atteso in _spans(SocialHandleRecognizer(), testo)


@pytest.mark.parametrize("testo", [
    "scrivi a m.rossi@studio.it per conferma",     # email, non handle
    "la email è nome@dominio.com",
    "prezzo @ 15 euro",                            # @ isolata (troppo corto)
    # Classe FP reale (OCR): email spezzata → resta solo "@dominio.tld".
    "contatta\n@iciuod.com per assistenza",
    "scrivi a\n@mocha.ni oggi",
])
def test_social_non_validi(testo):
    spans = _spans(SocialHandleRecognizer(), testo)
    assert spans == []


# ---------------------------------------------------------------------------
# DOCUMENTO IDENTITÀ (pattern; la keyword è richiesta a valle dal motore)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("testo,atteso", [
    ("carta d'identità AB 1234567 rilasciata dal Comune", "AB 1234567"),
    ("CIE n. CA00000AA valida", "CA00000AA"),
    ("passaporto YA1234567 in corso di validità", "YA1234567"),
    ("patente n. AB1234567C", "AB1234567C"),
    ("tessera sanitaria 80380500123456789012", "80380500123456789012"),
])
def test_documento_pattern_validi(testo, atteso):
    assert atteso in _spans(DocumentoIdentitaRecognizer(), testo)


def test_documento_pattern_non_valido():
    assert _spans(DocumentoIdentitaRecognizer(), "misura 12345678 mm") == []


# ---------------------------------------------------------------------------
# CASELLA POSTALE (→ INDIRIZZO)
# ---------------------------------------------------------------------------

def test_casella_postale_valida():
    testo = "spedire a C.P. 123, 06081 Assisi"
    assert "C.P. 123" in _spans(IndirizzoItalianoRecognizer(), testo)


def test_casella_postale_sigla_nuda_non_matcha():
    # "CP" senza punti è sigla generica: non deve matchare.
    assert not any(
        "CP 5" in s
        for s in _spans(IndirizzoItalianoRecognizer(), "il CP 5 del progetto")
    )


# ---------------------------------------------------------------------------
# End-to-end: categorie di default e sostituzione nel motore completo
# ---------------------------------------------------------------------------

def test_tassonomia_categorie_default():
    from backend.motore import CATEGORIE_DEFAULT_ATTIVE
    for c in ("TARGA", "VIN", "PRATICA", "SOCIAL"):
        assert c in CATEGORIE_DEFAULT_ATTIVE, f"{c} deve essere attiva di default"
    for c in ("MAC", "CRYPTO", "IP", "CATASTO"):
        assert c not in CATEGORIE_DEFAULT_ATTIVE, f"{c} deve restare opt-in"


def test_e2e_targa_frase_gate_finale(tmp_db, sessione):
    from backend.motore import anonimizza
    testo = "Ci vediamo alle otto, veniamo con l'auto targata FG771XD."
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "FG771XD" not in out
    assert any(e["tipo"] == "TARGA" for e in ents if not e.get("suggerito"))


def test_e2e_pratica_sentenza(tmp_db, sessione):
    from backend.motore import anonimizza
    testo = "Con sentenza n. 4521/2023 il Tribunale accoglieva il ricorso."
    out, ents = anonimizza(testo, sessione, db_path=tmp_db)
    assert "4521/2023" not in out
    assert any(e["tipo"] == "PRATICA" for e in ents if not e.get("suggerito"))


def test_e2e_roundtrip_nuovi_tipi(tmp_db, sessione):
    from backend.motore import anonimizza, deanonimizza
    testo = (
        "Veicolo targato FG771XD, telaio VIN ZFA1234567B123456, "
        "pratica n. 2024/88, profilo @mrossi_88."
    )
    anon, _ = anonimizza(testo, sessione, db_path=tmp_db)
    assert "FG771XD" not in anon and "ZFA1234567B123456" not in anon
    restored, report = deanonimizza(anon, sessione, db_path=tmp_db)
    assert restored == testo
    assert report["warning"] == []
