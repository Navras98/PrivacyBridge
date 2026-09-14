# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Custom Presidio recognizers per entità italiane.

Ogni recognizer usa regex + validatore aritmetico (checksum / carattere di controllo)
per abbassare i falsi positivi.
"""

from __future__ import annotations

import os
import re
from typing import ClassVar

from presidio_analyzer import (
    EntityRecognizer,
    Pattern,
    PatternRecognizer,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpArtifacts

# Toggle di benchmark: se PRIVACYBRIDGE_NO_FIX1=1 usa le regex PRE-FIX
# (IBAN italiana-only senza spazi, P.IVA senza spazi). Solo per misurazione.
_NO_FIX1 = bool(os.environ.get("PRIVACYBRIDGE_NO_FIX1"))
_NO_FIX3 = bool(os.environ.get("PRIVACYBRIDGE_NO_FIX3"))


# ---------------------------------------------------------------------------
# Guardrail: lo span deve coprire ESATTAMENTE l'entità
# ---------------------------------------------------------------------------

# Range di lunghezza attesi per tipo (span nel testo originale, dopo trim
# marginale ma con eventuali spazi interni ancora presenti). Il controllo
# esiste per intercettare regex mal fatte che catturano solo un PREFISSO
# dell'entità (fuga di dati: la coda dell'IBAN/CF/PIVA resterebbe in chiaro).
_SPAN_LEN_ATTESA = {
    # 16 = persona fisica; 11..13 = ente/condominio (11 cifre, con eventuali
    # spazi interni tipo "80012 33058 4").
    "IT_CODICE_FISCALE": (11, 16),
    "IT_PARTITA_IVA": (11, 13),          # 11 cifre, 12/13 con spazi interni
    "IT_IBAN": (15, 42),                 # 15..34 senza spazi, fino a ~42 con spazi ogni 4
}


def _span_lunghezza_valida(start: int, end: int, testo: str, tipo: str) -> bool:
    """Verifica che ``testo[start:end]`` abbia una lunghezza plausibile per
    ``tipo``. Serve come guardrail contro regex che catturano un prefisso.
    """
    lo, hi = _SPAN_LEN_ATTESA.get(tipo, (0, 10**9))
    n = end - start
    return lo <= n <= hi


# ---------------------------------------------------------------------------
# Codice Fiscale (16 caratteri esatti)
# ---------------------------------------------------------------------------

_CF_REGEX = re.compile(
    r"(?<![A-Za-z0-9])"
    r"[A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z]"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)

# CF per enti/condomini: 11 cifre. Ammette formattazione con singolo spazio
# (es. "80012 33058 4"). Non ha checksum universale (a differenza della
# partita IVA), quindi lo attiviamo solo in presenza di keyword contestuali.
_CF_ENTE_REGEX = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:"
    r"\d{11}"                                 # attaccato
    r"|\d{5}\s\d{5}\s\d"                      # 5+5+1
    r")"
    r"(?![A-Za-z0-9])"
)

_CF_ENTE_CONTEXT = (
    "codice fiscale", "cod. fiscale", "cod fiscale",
    "c.f.", "cf ", " cf:", " cf.", "c/f",
    "condominio", "ente", "onlus", "associazione",
    "società", "societa'", "parrocchia", "fondazione",
)

_CF_ODD = {
    "0": 1, "1": 0, "2": 5, "3": 7, "4": 9, "5": 13, "6": 15, "7": 17,
    "8": 19, "9": 21,
    "A": 1, "B": 0, "C": 5, "D": 7, "E": 9, "F": 13, "G": 15, "H": 17,
    "I": 19, "J": 21, "K": 2, "L": 4, "M": 18, "N": 20, "O": 11, "P": 3,
    "Q": 6, "R": 8, "S": 12, "T": 14, "U": 16, "V": 10, "W": 22, "X": 25,
    "Y": 24, "Z": 23,
}
_CF_EVEN = {
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9,
    "A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7,
    "I": 8, "J": 9, "K": 10, "L": 11, "M": 12, "N": 13, "O": 14, "P": 15,
    "Q": 16, "R": 17, "S": 18, "T": 19, "U": 20, "V": 21, "W": 22, "X": 23,
    "Y": 24, "Z": 25,
}
_CF_CHECK = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _cf_valido(cf: str) -> bool:
    cf = cf.upper()
    if len(cf) != 16:
        return False
    total = 0
    for i, ch in enumerate(cf[:15]):
        if (i + 1) % 2 == 1:
            total += _CF_ODD.get(ch, 0)
        else:
            total += _CF_EVEN.get(ch, 0)
    return _CF_CHECK[total % 26] == cf[15]


class CodiceFiscaleRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(
                name="codice_fiscale",
                regex=_CF_REGEX.pattern,
                score=0.4,
            ),
        ]
        # CF ente (11 cifre) e fallback formato sono parte della FIX 1:
        # con PRIVACYBRIDGE_NO_FIX1=1 (baseline benchmark) restano disattivati.
        if not _NO_FIX1:
            patterns.append(
                Pattern(
                    name="codice_fiscale_ente",
                    regex=_CF_ENTE_REGEX.pattern,
                    score=0.15,
                )
            )
        super().__init__(
            supported_entity="IT_CODICE_FISCALE",
            patterns=patterns,
            supported_language="it",
            context=["codice", "fiscale", "cf", "c.f.", "condominio", "ente"],
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            if not _span_lunghezza_valida(r.start, r.end, text, "IT_CODICE_FISCALE"):
                continue
            # Persona fisica: 16 caratteri con checksum mod-26.
            if len(candidate) == 16:
                if _cf_valido(candidate):
                    r.score = 0.95
                    validated.append(r)
                    continue
                # Fallback formato (parte della FIX 1): la regex già impone
                # il pattern rigido (6 lettere + 2 cifre + 1 lettera mese + ...).
                # Un match che rispetta il pattern ma sbaglia il checksum è
                # quasi sempre un CF fake o con typo. Manteniamo l'entità con
                # score inferiore per non leakare dati che sembrano un CF.
                if not _NO_FIX1:
                    r.score = 0.6
                    validated.append(r)
                continue
            # Ente/condominio: 11 cifre (o 5+5+1 con spazi). Non c'è un
            # checksum universale, richiediamo contesto.
            cifre = re.sub(r"\s+", "", candidate)
            if len(cifre) != 11 or not cifre.isdigit():
                continue
            lo = max(0, r.start - 40)
            hi = min(len(text), r.end + 20)
            ctx = text[lo:hi].lower()
            if any(k in ctx for k in _CF_ENTE_CONTEXT):
                r.score = 0.85
                validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# Partita IVA italiana (11 cifre, checksum Luhn-like). Supporta anche
# formattazioni con singolo spazio ogni 4/5 cifre (es. "01234 567890").
# ---------------------------------------------------------------------------

if _NO_FIX1:
    # PRE-FIX (baseline): 11 cifre attaccate, senza spazi.
    _PIVA_REGEX = re.compile(r"(?<!\d)\d{11}(?!\d)")
else:
    _PIVA_REGEX = re.compile(
        r"(?<![A-Za-z0-9])"
        r"(?:"
        r"\d{11}"                       # attaccata
        r"|\d{5}\s\d{5}\s\d"            # 5+5+1 con spazi
        r"|\d{4}\s\d{4}\s\d{3}"         # 4+4+3 con spazi
        r"|\d{3}\s\d{3}\s\d{3}\s\d{2}"  # 3+3+3+2
        r")"
        r"(?![A-Za-z0-9])"
    )


def _piva_valida(piva: str) -> bool:
    # Rimuovo eventuali spazi interni (formato "01234 56789 0").
    piva = re.sub(r"\s+", "", piva)
    if len(piva) != 11 or not piva.isdigit():
        return False
    total = 0
    for i, digit in enumerate(piva[:10]):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    check = (10 - (total % 10)) % 10
    return check == int(piva[10])


_PIVA_CONTEXT = (
    "partita iva", "p.iva", "p. iva", "piva", "iva ", " iva.", " iva:",
    "vat", "codice iva",
)


class PartitaIVARecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(
                name="partita_iva",
                regex=_PIVA_REGEX.pattern,
                score=0.3,
            )
        ]
        super().__init__(
            supported_entity="IT_PARTITA_IVA",
            patterns=patterns,
            supported_language="it",
            context=["partita", "iva", "p.iva", "piva", "vat"],
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            if not _span_lunghezza_valida(r.start, r.end, text, "IT_PARTITA_IVA"):
                continue
            if _piva_valida(candidate):
                r.score = 0.9
                validated.append(r)
                continue
            # Fallback formato (parte della FIX 1): 11 cifre non validate al
            # checksum sono spesso PIVA fake/typo. Le accettiamo con score
            # inferiore SOLO se il contesto contiene una keyword esplicita
            # (p.iva / partita iva / vat): senza keyword il rischio di falso
            # positivo è alto (date, tracking, ecc.).
            if _NO_FIX1:
                continue
            lo = max(0, r.start - 40)
            hi = min(len(text), r.end + 20)
            ctx = text[lo:hi].lower()
            if any(k in ctx for k in _PIVA_CONTEXT):
                r.score = 0.7
                validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# IBAN internazionale (15-34 caratteri, checksum ISO 7064 mod 97).
#
# Supporta:
#  - forma attaccata: IT60X0542811101000012345678
#  - forma con spazi ogni 4 char: IT60 X054 2811 1010 0000 1234 5678
#  - qualunque paese: DE89370400440532013000, FR7630006000011234567890189,
#    ES9121000418450200051332, GB29NWBK60161331926819, CH9300762011623852957,
#    NL91ABNA0417164300
#  - case-insensitive (input utente può essere in minuscolo)
#
# La regex cattura anche prefissi non-IBAN (11..30 alfanumerici post ISO+check):
# il vero filtro è la validazione mod 97 in ``_iban_valido``.
# ---------------------------------------------------------------------------

# Due varianti:
#  - attaccata: 15..34 caratteri alfanumerici consecutivi (paese+check+BBAN)
#  - con spazi: gruppi di 4 caratteri, opzionale gruppo finale corto (2-4).
# La seconda variante è tipica della stampa "IT60 X054 2811 1010 0000 1234 5678"
# ed evita di catturare parole successive per "greedy overshoot".
if _NO_FIX1:
    # PRE-FIX (baseline benchmark): IBAN italiano-only, no spazi.
    _IBAN_REGEX = re.compile(
        r"\bIT\d{2}[A-Z]\d{10}[A-Z0-9]{12}\b",
        re.IGNORECASE,
    )
else:
    _IBAN_REGEX = re.compile(
        r"(?<![A-Za-z0-9])"
        r"(?:"
        r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}"
        r"|[A-Z]{2}\d{2}(?:\s[A-Z0-9]{4}){2,7}(?:\s[A-Z0-9]{1,4})?"
        r")"
        r"(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


# Lunghezze IBAN per paese (registro ISO 13616). Se il paese è noto e la
# lunghezza è quella ufficiale, il formato è già molto discriminante.
_IBAN_LEN_PER_PAESE = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16,
    "BG": 22, "BH": 22, "BR": 29, "BY": 28, "CH": 21, "CR": 22, "CY": 28,
    "CZ": 24, "DE": 22, "DK": 18, "DO": 28, "EE": 20, "EG": 29, "ES": 24,
    "FI": 18, "FO": 18, "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18,
    "GR": 27, "GT": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23,
    "IS": 26, "IT": 27, "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32,
    "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MD": 24, "ME": 22,
    "MK": 19, "MR": 27, "MT": 31, "MU": 30, "NL": 18, "NO": 15, "PK": 24,
    "PL": 28, "PS": 29, "PT": 25, "QA": 29, "RO": 24, "RS": 22, "SA": 24,
    "SC": 31, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "ST": 25, "SV": 28,
    "TL": 23, "TN": 24, "TR": 26, "UA": 29, "VA": 22, "VG": 24, "XK": 20,
}


def _iban_mod97(iban_norm: str) -> int | None:
    """Ritorna ``int(numeric) % 97`` per un IBAN già normalizzato (upper, no spaces),
    o None se non è convertibile.
    """
    rearranged = iban_norm[4:] + iban_norm[:4]
    numeric = ""
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        elif ch.isalpha():
            numeric += str(ord(ch) - 55)
        else:
            return None
    try:
        return int(numeric) % 97
    except ValueError:
        return None


def _iban_forma_valida(iban: str, strict_paese: bool = False) -> bool:
    """True se ``iban`` (dopo trim di spazi e upper) rispetta la forma di base:
    2 lettere paese + 2 cifre controllo + 11..30 alfanumerici (15..34 tot).

    Con ``strict_paese=True`` verifica anche la lunghezza esatta prevista per
    il paese (registro ISO 13616). Con ``strict_paese=False`` (default) è
    tollerante: utile per dati di test o input con formattazione anomala.
    """
    iban = iban.replace(" ", "").upper()
    if not (15 <= len(iban) <= 34):
        return False
    if not (iban[:2].isalpha() and iban[2:4].isdigit()):
        return False
    if not iban[4:].isalnum():
        return False
    if strict_paese:
        atteso = _IBAN_LEN_PER_PAESE.get(iban[:2])
        if atteso is not None and len(iban) != atteso:
            return False
    return True


def _iban_valido(iban: str) -> bool:
    """Checksum mod-97 (ISO 7064). True se l'IBAN è aritmeticamente valido."""
    iban = iban.replace(" ", "").upper()
    if len(iban) < 15 or len(iban) > 34:
        return False
    m = _iban_mod97(iban)
    return m == 1


class IBANItalianoRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(
                name="iban",
                regex=_IBAN_REGEX.pattern,
                score=0.5,
            )
        ]
        super().__init__(
            supported_entity="IT_IBAN",
            patterns=patterns,
            supported_language="it",
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            if not _span_lunghezza_valida(r.start, r.end, text, "IT_IBAN"):
                continue
            # Checksum valido: alta confidenza.
            if _iban_valido(candidate):
                r.score = 0.95
                validated.append(r)
                continue
            # Format-only fallback (parte della FIX 1): IBAN plausibile
            # (paese + lunghezza). Serve per PII detection sicura anche con
            # dati di test/fake. Meglio anonimizzare un finto-IBAN che leakare
            # un vero IBAN scritto con un typo (uno swap di cifre falsifica
            # il checksum ma non cambia la sensibilità del dato).
            if _NO_FIX1:
                continue
            if _iban_forma_valida(candidate):
                r.score = 0.6
                validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# Telefono italiano (fisso o mobile, con o senza +39)
# ---------------------------------------------------------------------------

# BUG-real 3b: regex stringente per evitare cattura di:
#  - tariffe decimali ("0,14 0,28"): virgola come separatore decimale
#  - metriche ("0.987 0.990"): punto come separatore decimale
#  - anni ("1689"): 4 cifre senza prefisso
# Vincoli:
#  - Prefisso OBBLIGATORIO: +39, 0039, 0 (fisso), oppure 3xx (mobile)
#  - Separatori: whitespace, trattino, punto, barra — NO virgola
#  - Look-around anti-decimale: nessun `.` o `,` immediatamente
#    prima o dopo (esclude i decimali come 0,14 e 0.987)
# Look-around anti-decimale MIRATO: virgola/punto bloccano il match solo
# quando adiacenti a una cifra (decimali "0,14"/"0.987"); la punteggiatura
# di frase (", 3391234567," con spazio) non deve bloccare — classe di FP
# trovata dalla suite avversariale.
#
# Punto e barra fra i separatori: l'audit di precisione (AUDIT_PRECISIONE.md
# § 3.A) ha trovato tre numeri lasciati in chiaro su documento reale —
# "075/9115329" dopo "tel.", "075.5098004" dopo "n. di fax" — di cui due
# già mascherati altrove nello stesso documento nella forma con lo spazio.
# La stessa cifra scritta in due modi dava due esiti diversi.  Le date e i
# decimali continuano a essere esclusi perché i look-around guardano le
# cifre adiacenti, non i separatori interni.
_TEL_IT_REGEX = re.compile(
    r"(?<!\w)(?<!\d,)(?<!\d\.)(?<!\d/)"
    r"(?:"
    r"(?:\+39|0039)[\s\-./]?[0-9](?:[\s\-./]?[0-9]){7,10}"  # +39 / 0039 + 8-11 cifre
    r"|3[0-9]{2}[\s\-./]?[0-9]{3}[\s\-./]?[0-9]{3,4}"       # mobile 3xx xxx xxxx
    r"|0[0-9]{1,3}[\s\-./]?[0-9]{5,8}"                      # fisso 0xxx xxxxxxx
    r")"
    r"(?!\w)(?!,\d)(?!\.\d)(?!/\d)"
)


class TelefonoItalianoRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(
                name="tel_it",
                regex=_TEL_IT_REGEX.pattern,
                score=0.5,
            )
        ]
        super().__init__(
            supported_entity="IT_TELEFONO",
            patterns=patterns,
            supported_language="it",
            context=["telefono", "tel", "cell", "cellulare", "phone", "mobile"],
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            digits = re.sub(r"\D", "", candidate)
            if candidate.startswith("+39"):
                digits_no_pref = digits.removeprefix("39")
            else:
                digits_no_pref = digits
            if 6 <= len(digits_no_pref) <= 13:
                r.score = 0.85
                validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# CAP italiano
# ---------------------------------------------------------------------------

_CAP_REGEX = re.compile(r"(?<!\d)\d{5}(?!\d)")

# Estremi dei CAP assegnati in Italia: 00010 (Roma, Colonna) e 98168
# (Messina). Confrontati come interi, quindi lo zero iniziale cade.
# Servono a scartare i cinque-cifre che CAP non sono: importi, matricole,
# anni con le migliaia attaccate.
_CAP_MIN = 10
_CAP_MAX = 98168


class CAPItalianoRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(
                name="cap_it",
                regex=_CAP_REGEX.pattern,
                score=0.2,
            )
        ]
        super().__init__(
            supported_entity="IT_CAP",
            patterns=patterns,
            supported_language="it",
            context=["cap", "codice", "postale", "via", "corso", "piazza"],
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            try:
                n = int(candidate)
            except ValueError:
                continue
            if _CAP_MIN <= n <= _CAP_MAX:
                # Contesto obbligatorio: guarda parole vicine.
                lo = max(0, r.start - 40)
                hi = min(len(text), r.end + 20)
                ctx = text[lo:hi].lower()
                if any(k in ctx for k in ("cap", "via ", "corso ", "piazza ",
                                          "viale", "postale")):
                    r.score = 0.7
                    validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# Nome + Cognome italiano (regex generica, fallback quando spaCy fallisce)
# ---------------------------------------------------------------------------

# Nome/Cognome iniziano con maiuscola. Ammette particelle: De, Del, Della,
# Di, Da, Dal, Dalla, La, Lo, Le, Li, Su. Esclude parole d'apertura frase
# comuni tramite score basso e post-filtering di whitelist.
_NAME_TOKEN = r"(?:D[aeio]l?l?[ae]?|La|Lo|Le|Li|Su|Van|Von|De)"
_CAP_WORD = r"[A-ZÀ-Ý][a-zà-ÿ']+"
_NOME_COGNOME_REGEX = re.compile(
    rf"\b{_CAP_WORD}(?:\s{_NAME_TOKEN})?\s{_CAP_WORD}(?:\s{_CAP_WORD})?\b"
)

# Parole che spesso iniziano frase ma non sono nomi propri.
_STOPWORDS_INIZIO_FRASE = {
    "Il", "Lo", "La", "I", "Gli", "Le", "Un", "Uno", "Una",
    "Questo", "Questa", "Quello", "Quella",
    "Mio", "Mia", "Tuo", "Tua", "Suo", "Sua", "Nostro", "Vostro",
    "Signor", "Signora", "Signorina", "Sig", "Dott", "Dr", "Prof",
    "Egr", "Spett", "Gentile", "Caro", "Cara",
    "Grazie", "Ciao", "Salve", "Buongiorno", "Buonasera", "Buonanotte",
    "Cordiali", "Distinti", "Saluti", "Cari", "Care",
    "Oggi", "Ieri", "Domani",
    "Roma", "Milano", "Napoli", "Torino", "Firenze", "Venezia", "Bologna",
    "Genova", "Palermo", "Bari", "Verona", "Catania",
    # Odonimi: "Via Manzoni" ha la stessa forma di "Nome Cognome" ma è un
    # indirizzo, e PERSONA ha priorità su LUOGO in _risolvi_sovrapposizioni.
    "Via", "Viale", "Piazza", "Piazzale", "Corso", "Largo", "Vicolo",
    "Strada", "Vico", "Contrada", "Frazione", "Località", "Borgo",
    "Lungomare", "Salita", "Traversa",
}


class NomeCognomeRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(
                name="nome_cognome",
                regex=_NOME_COGNOME_REGEX.pattern,
                score=0.35,
            )
        ]
        super().__init__(
            supported_entity="IT_NOME_COGNOME",
            patterns=patterns,
            supported_language="it",
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            first_word = candidate.split()[0]
            if first_word in _STOPWORDS_INIZIO_FRASE:
                continue
            validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------

_URL_REGEX = re.compile(
    r"https?://[^\s<>\"']+|www\.[^\s<>\"']+",
    re.IGNORECASE,
)


class URLRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [Pattern(name="url", regex=_URL_REGEX.pattern, score=0.85)]
        super().__init__(
            supported_entity="URL",
            patterns=patterns,
            supported_language="it",
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            if candidate.startswith(("http://", "https://", "www.")):
                r.score = 0.95
                validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# Indirizzo IPv4
# ---------------------------------------------------------------------------

_IP_REGEX = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)


class IPRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [Pattern(name="ip", regex=_IP_REGEX.pattern, score=0.85)]
        super().__init__(
            supported_entity="IP_ADDRESS",
            patterns=patterns,
            supported_language="it",
        )


# ---------------------------------------------------------------------------
# Date italiane
# ---------------------------------------------------------------------------

# 12/03/1985, 12-03-1985, 12.03.1985, 1985-03-12, 12 marzo 1985, 12 mar 85,
# marzo 2024. Il flag inline (?i) è necessario perché Presidio ricompila il
# pattern con i propri flag globali, scartando quelli del re.compile locale.
_MESE = (
    r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|"
    r"luglio|agosto|settembre|ottobre|novembre|dicembre)"
)
_GIORNO_SETT = r"(?:luned[ìi]|marted[ìi]|mercoled[ìi]|gioved[ìi]|venerd[ìi]|sabato|domenica)"

_DATA_IT_REGEX = re.compile(
    r"(?i)"
    r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b"
    r"|\b\d{4}[/\-.]\d{2}[/\-.]\d{2}\b"
    # Giorno della settimana, eventualmente seguito da "9 giugno [2025]".
    rf"|\b{_GIORNO_SETT}(?:\s+\d{{1,2}}\s+{_MESE}(?:\s+(?:del\s+)?\d{{2,4}})?)?\b"
    # "12 marzo 1985", "12 marzo del 1985" e "3 aprile" (anno implicito).
    rf"|\b\d{{1,2}}\s+{_MESE}(?:\s+(?:del\s+)?\d{{2,4}})?\b"
    # Mese abbreviato: l'anno resta obbligatorio, "3 mar" è troppo ambiguo.
    r"|\b\d{1,2}\s+(?:gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic)\s+(?:del\s+)?\d{2,4}\b"
    rf"|\b{_MESE}\s+(?:del\s+)?\d{{4}}\b"
)


class DataItalianaRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="data_it", regex=_DATA_IT_REGEX.pattern, score=0.8)
        ]
        super().__init__(
            supported_entity="DATE_TIME",
            patterns=patterns,
            supported_language="it",
            context=["data", "nato", "nata", "il", "del", "dal", "al", "scadenza"],
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        for r in results:
            r.score = 0.95
        return results


# ---------------------------------------------------------------------------
# Data di nascita (categoria dedicata, attiva per default)
# ---------------------------------------------------------------------------
#
# Una data di nascita è un dato personale in senso proprio, e va
# distinta dalle date generiche (che sono spente per default). Il
# recognizer cerca la data all'interno di uno dei pattern di contesto
# tipici:
#   "nato il", "nata il", "nato a X il", "data di nascita",
#   "n. il", "d.d.n.".
# La cattura include l'intera data (giorno + mese + anno) per non
# lasciare fuori il giorno.

_CONTESTO_NASCITA_REGEX = re.compile(
    r"(?i)"
    r"(?:"
    # "nato a X il", "nato ad X il" (con articolo davanti a vocale).
    r"nat[oa]\s+ad?\s+[A-ZÀ-Ýa-zà-ÿ']+(?:\s+[A-ZÀ-Ýa-zà-ÿ']+)?\s+il|"
    r"nat[oa]\s+il|"
    r"data\s+di\s+nascita\s*:?|"
    r"n\.?\s+il|"
    r"d\.?d\.?n\.?\s*:?|"
    r"nascita\s*:?|"
    r"nat[oa]\s+in\s+data|"
    r"nasce\s+il"
    r")"
    r"\s+(" + _DATA_IT_REGEX.pattern.replace("(?i)", "") + r")"
)


# ---------------------------------------------------------------------------
# Luogo di nascita / residenza (categoria anagrafica, attiva per default)
# ---------------------------------------------------------------------------
#
# Simmetrico a DataNascitaRecognizer: il toponimo di nascita/residenza è
# dato anagrafico (insieme a nome + data di nascita si deriva il CF).
# Con LUOGO generico spento per default, senza questa categoria il comune
# di nascita usciva sempre in chiaro.
#
# La categoria copre anche "residente a X", "domiciliato a Y",
# "originario di Z": tutti toponimi in contesto anagrafico.
# È etichettata LUOGO_NASCITA per uniformità col caso principale, ma
# funge da "luogo anagrafico" più in generale (annotato in DECISIONI.md).

# Contesti che aprono un toponimo anagrafico.
_CONTESTO_LUOGO_NASCITA = re.compile(
    r"(?i)"
    r"(?:"
    # Forme con "in provincia di X" / "nel comune di X" — anteposte
    # perché più specifiche: catturano solo il toponimo dopo "di".
    r"(?:nat[oa]|nasce|residente|domiciliat[oa]|originari[oa])"
    r"\s+(?:in|nel|nella|nello|nei|negli|nelle|del|dello|della|dei|delle|degli)"
    r"\s+(?:provincia|regione|comune|città|zona)"
    r"(?:\s+di)?(?=\s)|"
    # Forme dirette "nato a X", "nato ad X", "nato in X". Il (?=\s)
    # finale evita match come "sto a" dentro "sto andando".
    r"nat[oa]\s+(?:ad?|in|nel|nella|presso)(?=\s)|"
    r"nasce\s+(?:ad?|in|nel|nella|presso)(?=\s)|"
    r"residente\s+(?:ad?|in|nel|nella|presso|a)(?=\s)|"
    r"domiciliat[oa]\s+(?:ad?|in|nel|nella|presso|a)(?=\s)|"
    r"originari[oa]\s+(?:di|d')(?=\s|[A-ZÀ-Ýa-zà-ÿ])|"
    # Verbi di abitazione: lista finita di forme comuni.
    # ESCLUSI: sto/stai/sta/stiamo/state/stanno perché "sta a", "stanno
    # in", "state in" sono sequenze italiane comuni che non indicano
    # residenza (BUG reale su documenti utente).
    r"(?:abito|abita|abitiamo|abitate|abitano|"
    r"vivo|vive|vivi|viviamo|vivete|vivono|"
    r"risiedo|risiede|risiedi|risiediamo|risiedete|risiedono)"
    r"\s+(?:ad?|in|nel|nella|presso|a)(?=\s)|"
    # Campo etichettato.
    r"luogo\s+di\s+nascita\s*:?|"
    r"comune\s+di\s+nascita\s*:?|"
    r"provincia\s+di\s+nascita\s*:?|"
    r"paese\s+di\s+nascita\s*:?"
    r")"
)

# Parole che terminano il toponimo (avanzando token per token): la data,
# la punteggiatura forte, congiunzioni, verbi.
_STOP_TOPONIMO = {
    "il", "l'", "lo", "la", "i", "gli", "le",
    "in", "a", "ad", "da", "di", "del", "dello", "della", "delle",
    "degli", "dei", "dal", "dalla", "dallo", "dalle", "dagli", "dai",
    "con", "per", "tra", "fra", "su", "sul", "sulla", "sullo",
    "e", "ed", "o", "od", "ma", "però",
    "che", "chi", "cui", "come", "quando", "dove", "perché",
    "è", "sono", "ho", "ha", "hai", "abbiamo", "avete", "hanno",
    "sei", "siete", "siamo", "era", "sarà",
    "un", "una", "uno",
    "nato", "nata", "nasce",
    "residente", "domiciliato", "originario", "presso",
}

# Connettori toponimici ammessi in mezzo a un toponimo multi-parola
# ("Reggio nell'Emilia", "San Giovanni Valdarno", "Bagno a Ripoli").
_CONNETTORI_TOPONIMO = {
    "di", "del", "della", "delle", "dello", "degli", "dei",
    "a", "al", "alla", "allo", "alle", "agli", "ai",
    "in", "nel", "nella", "nello", "nelle", "negli", "nei",
    "d'", "dell'", "dall'", "nell'", "sull'", "all'",
    "sant'", "san", "santa", "santo", "santi", "sante", "ss.",
    "sotto", "sopra", "presso", "monte", "monti", "colle", "valle",
    "val", "ponte", "bagno", "campo",
}


class LuogoNascitaRecognizer(EntityRecognizer):
    """Toponimo in contesto anagrafico (nascita/residenza/origine).

    Approccio non-PatternRecognizer perché l'estrazione del toponimo
    richiede parsing token-per-token con filtro stop-word (evita di
    catturare l'intero "roma il 15 maggio del 1975" al posto di
    "assisi").
    """

    def __init__(self):
        super().__init__(
            supported_entities=["IT_LUOGO_NASCITA"],
            supported_language="it",
            name="LuogoNascitaRecognizer",
        )

    def load(self) -> None:  # pragma: no cover
        return None

    _TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']*")

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        results: list[RecognizerResult] = []
        for ctx_m in _CONTESTO_LUOGO_NASCITA.finditer(text):
            cursor = ctx_m.end()
            # Salta spazi/virgole.
            while cursor < len(text) and text[cursor] in " \t,:":
                cursor += 1
            if cursor >= len(text):
                continue

            # Primo token: obbligatorio, alfabetico, ≥ 2 caratteri.
            m1 = self._TOKEN_RE.match(text, cursor)
            if m1 is None:
                continue
            first_tok = m1.group(0)
            first_lc = first_tok.lower().rstrip("'")
            if first_lc in _STOP_TOPONIMO or len(first_tok) < 2:
                continue

            span_start = m1.start()
            span_end = m1.end()

            # Determina se il primo token è capitalizzato (per il
            # criterio multi-parola).
            primo_cap = first_tok[0].isupper()

            # Prova a estendere fino a 3 token in più.
            j = m1.end()
            estensioni = 0
            while estensioni < 3:
                # Skip spazi (uno solo consentito fra token).
                k = j
                while k < len(text) and text[k] == " ":
                    k += 1
                if k == j:  # niente spazio, fine toponimo
                    break
                m_next = self._TOKEN_RE.match(text, k)
                if m_next is None:
                    break
                tok = m_next.group(0)
                tok_lc = tok.lower().rstrip("'")

                # Stop-word: chiudi il toponimo prima.
                if tok_lc in _STOP_TOPONIMO:
                    break

                # Connettore: continua a prendere altri token.
                if tok_lc in _CONNETTORI_TOPONIMO or tok.endswith("'"):
                    j = m_next.end()
                    estensioni += 1
                    continue

                # Token capitalizzato: estende il toponimo (Reggio Emilia).
                if tok[0].isupper():
                    span_end = m_next.end()
                    j = m_next.end()
                    estensioni += 1
                    continue

                # In minuscolo (dopo un token minuscolo iniziale): estendi
                # ancora fino a 1 token per gestire "reggio emilia" tutto
                # in minuscolo, ma solo se il PRIMO era minuscolo.
                if not primo_cap and estensioni == 0:
                    span_end = m_next.end()
                    j = m_next.end()
                    estensioni += 1
                    continue

                break

            results.append(
                RecognizerResult(
                    entity_type="IT_LUOGO_NASCITA",
                    start=span_start,
                    end=span_end,
                    score=0.9,
                )
            )
        return results


class DataNascitaRecognizer(PatternRecognizer):
    """Cattura date di nascita — sottoinsieme di DATE_TIME identificate
    dal contesto ("nato il", "nata a X il", "data di nascita", ...)."""

    def __init__(self):
        # Pattern: contesto + data. Presidio ricompila il regex; usiamo
        # il pattern completo.
        patterns = [
            Pattern(
                name="data_nascita",
                regex=_CONTESTO_NASCITA_REGEX.pattern,
                score=0.9,
            )
        ]
        super().__init__(
            supported_entity="IT_DATA_NASCITA",
            patterns=patterns,
            supported_language="it",
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        # Non usiamo super().analyze perché vogliamo restringere lo span
        # alla SOLA data (senza il contesto "nato il").
        results: list[RecognizerResult] = []
        for m in _CONTESTO_NASCITA_REGEX.finditer(text):
            data_start = m.start(1)
            data_end = m.end(1)
            results.append(
                RecognizerResult(
                    entity_type="IT_DATA_NASCITA",
                    start=data_start,
                    end=data_end,
                    score=0.95,
                )
            )
        return results


# ---------------------------------------------------------------------------
# Indirizzi italiani (odonimo + toponimo + civico)
# ---------------------------------------------------------------------------

# Indirizzo italiano: odonimo + toponimo + civico.
# Vincoli difensivi:
#  - ``[ \t]`` (non ``\s``): non attraversiamo newline ("via curl\n4"
#    non è un indirizzo).
#  - Il toponimo è puramente alfabetico (no cifre): "OAuth2" NON è
#    un toponimo, "OAuth" con "2" attaccato NON è un civico separato.
#  - Fra toponimo e civico serve almeno UNO spazio o virgola+spazio
#    (rifiuta "OAuth2" letto come "OAuth" + "2").
_INDIRIZZO_REGEX = re.compile(
    r"\b(?:Via|Viale|Vle|Piazza|P\.za|Piazzale|Corso|C\.so|Largo|Vicolo|Strada|"
    r"Boulevard|Vico|Contrada|Frazione|Località|L\.go|P\.le)"
    r"[ \t]+[A-ZÀ-Ý][a-zà-ÿ']+(?:[ \t]+[A-ZÀ-Ý][a-zà-ÿ']+)*"
    r"(?:[ \t]*,)?[ \t]+\d{1,4}[A-Z]?\b"
)


# Casella postale: "C.P. 123", "Casella Postale 4567". Il pattern
# "CP" senza punti è troppo ambiguo (sigla generica) e resta escluso.
_CASELLA_POSTALE_REGEX = re.compile(
    r"(?i)\b(?:c\.p\.|casella\s+postale)\s*(?:n\.?\s*)?\d{1,5}\b"
)


class IndirizzoItalianoRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="indirizzo_it", regex=_INDIRIZZO_REGEX.pattern, score=0.7),
            Pattern(name="casella_postale", regex=_CASELLA_POSTALE_REGEX.pattern, score=0.7),
        ]
        super().__init__(
            supported_entity="IT_INDIRIZZO",
            patterns=patterns,
            supported_language="it",
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        for r in results:
            r.score = 0.9
        return results


# ---------------------------------------------------------------------------
# Numeri di spedizione (UPS / BRT / DHL / SDA / GLS)
# ---------------------------------------------------------------------------

# UPS: prefisso "1Z" + 16 caratteri alfanumerici. Pattern univoco, senza
# necessità di contesto.
_TRK_UPS_REGEX = re.compile(r"(?<![A-Za-z0-9])1Z[A-Z0-9]{16}(?![A-Za-z0-9])")

# GLS-Italy: prefisso "GLSIT" (o "GLS") + 8-12 cifre.
_TRK_GLS_REGEX = re.compile(
    r"(?<![A-Za-z0-9])GLS(?:IT)?\d{8,12}(?![A-Za-z0-9])",
    re.IGNORECASE,
)

# BRT / DHL / SDA: sequenze di 8-12 cifre. Da soli sarebbero indistinguibili
# da altri numeri (CAP, telefono breve...); li abilitiamo solo quando c'è
# contesto esplicito nelle vicinanze (parola corriere o "tracking"/"spedizione").
_TRK_GENERIC_REGEX = re.compile(r"(?<!\d)\d{8,12}(?!\d)")

_TRK_CONTEXT_KEYWORDS = (
    "brt", "dhl", "sda", "gls", "poste", "bartolini", "corriere",
    "tracking", "spedizione", "spedito", "ddt",
)


class NumeroSpedizioneRecognizer(PatternRecognizer):
    """Recognizer per numeri di tracking spedizioni: UPS, GLS, BRT, DHL, SDA."""

    def __init__(self):
        patterns = [
            Pattern(name="trk_ups", regex=_TRK_UPS_REGEX.pattern, score=0.9),
            Pattern(name="trk_gls", regex=_TRK_GLS_REGEX.pattern, score=0.9),
            # Il pattern generico ha score basso; sarà validato dal contesto.
            Pattern(name="trk_gen", regex=_TRK_GENERIC_REGEX.pattern, score=0.2),
        ]
        super().__init__(
            supported_entity="IT_NUMERO_SPEDIZIONE",
            patterns=patterns,
            supported_language="it",
            context=list(_TRK_CONTEXT_KEYWORDS),
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            # UPS / GLS: pattern univoco, accettiamo senza altra verifica.
            if candidate.upper().startswith(("1Z", "GLS")):
                r.score = 0.95
                validated.append(r)
                continue
            # Generico 8-12 cifre: serve keyword nelle vicinanze.
            lo = max(0, r.start - 40)
            hi = min(len(text), r.end + 20)
            ctx = text[lo:hi].lower()
            if any(k in ctx for k in _TRK_CONTEXT_KEYWORDS):
                r.score = 0.75
                validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# Targa italiana (auto moderna, moto, storica provinciale, ciclomotore)
# ---------------------------------------------------------------------------
#
# Formato auto moderno (dal 1994): 2 lettere + 3 cifre + 2 lettere, con
# alfabeto ridotto (esclude I, O, Q, U per leggibilità). Il formato è
# abbastanza specifico da non richiedere contesto ("FG771XD").
# Ammessi separatori spazio o trattino fra i gruppi ("FG 771 XD",
# "FG-771-XD"): scritture comuni a mano.
#
# Formati che RICHIEDONO keyword di contesto (troppo generici da soli):
#  - moto (dal 1999): 2 lettere + 5 cifre ("BA 12345")
#  - storica provinciale: sigla provincia + 6 cifre ("MI 123456")
#  - ciclomotore: 5-6 alfanumerici ("X2CD34")

_TARGA_LETTERE = "ABCDEFGHJKLMNPRSTVWXYZ"

_TARGA_AUTO_REGEX = re.compile(
    rf"(?<![A-Za-z0-9])"
    rf"[{_TARGA_LETTERE}]{{2}}[ \-]?\d{{3}}[ \-]?[{_TARGA_LETTERE}]{{2}}"
    rf"(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_TARGA_CTX_REGEX = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:"
    r"[A-Z]{2}[ \-]?\d{5,6}"      # moto (5 cifre) / storica (6 cifre)
    r"|[A-Z0-9]{5,7}"             # ciclomotore e formati speciali
    r")"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_TARGA_KEYWORDS = (
    "targa", "targat", "veicolo", "automobile", "autovettura",
    "motociclo", "moto ", "ciclomotore", "rimorchio", "immatricolat",
)


class TargaItalianaRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="targa_auto", regex=_TARGA_AUTO_REGEX.pattern, score=0.6),
            Pattern(name="targa_ctx", regex=_TARGA_CTX_REGEX.pattern, score=0.2),
        ]
        super().__init__(
            supported_entity="IT_TARGA",
            patterns=patterns,
            supported_language="it",
            context=["targa", "targata", "veicolo", "auto", "moto"],
        )

    # Unità di misura che chiudono spesso "sigla numero unità" nei
    # documenti tecnici ("main.py 199 KB", "potenza 90 CV"): mai targhe.
    _UNITA: ClassVar[set[str]] = {
        "KB", "MB", "GB", "TB", "KM", "KG", "MM", "CM", "MT",
        "HZ", "KW", "CV", "HP", "MQ", "ML", "DB", "PT", "PX",
    }

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            compatto = re.sub(r"[ \-]", "", candidate).upper()
            separata = bool(re.search(r"[ \-]", candidate))
            # Formato auto moderno: accettato anche senza keyword.
            if re.fullmatch(
                rf"[{_TARGA_LETTERE}]{{2}}\d{{3}}[{_TARGA_LETTERE}]{{2}}", compatto
            ):
                if separata:
                    # Con separatori il pattern diventa permissivo
                    # ("py 199 KB" nei doc tecnici): richiediamo che le
                    # lettere siano TUTTE maiuscole nel testo originale
                    # e che i gruppi letterali non siano unità di misura
                    # — a meno che una keyword veicolare non tolga ogni
                    # dubbio ("targa AB 123 CV").
                    lettere = [c for c in candidate if c.isalpha()]
                    if not all(c.isupper() for c in lettere):
                        continue
                    if compatto[-2:] in self._UNITA or compatto[:2] in self._UNITA:
                        lo = max(0, r.start - 40)
                        ctx = text[lo:r.start].lower()
                        if not any(k in ctx for k in _TARGA_KEYWORDS):
                            continue
                r.score = 0.9
                validated.append(r)
                continue
            # Altri formati: keyword obbligatoria nelle vicinanze.
            lo = max(0, r.start - 40)
            hi = min(len(text), r.end + 20)
            ctx = text[lo:hi].lower()
            # Deve contenere sia lettere che cifre (esclude parole e numeri
            # puri catturati dal pattern ciclomotore).
            if (any(k in ctx for k in _TARGA_KEYWORDS)
                    and any(c.isdigit() for c in compatto)
                    and any(c.isalpha() for c in compatto)):
                r.score = 0.8
                validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# VIN — numero di telaio (17 caratteri, alfabeto senza I/O/Q)
# ---------------------------------------------------------------------------
#
# Il VIN è deterministico nel formato ma un blob di 17 alfanumerici può
# comparire anche in contesti tecnici (hash, ID). Richiediamo la keyword
# ("telaio", "vin", "chassis") nelle vicinanze.

_VIN_REGEX = re.compile(
    r"(?<![A-Za-z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_VIN_KEYWORDS = ("telaio", "vin", "chassis")


class VINRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [Pattern(name="vin", regex=_VIN_REGEX.pattern, score=0.3)]
        super().__init__(
            supported_entity="IT_VIN",
            patterns=patterns,
            supported_language="it",
            context=["telaio", "vin", "chassis"],
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end].upper()
            if not (any(c.isdigit() for c in candidate)
                    and any(c.isalpha() for c in candidate)):
                continue
            lo = max(0, r.start - 40)
            hi = min(len(text), r.end + 20)
            ctx = text[lo:hi].lower()
            if any(k in ctx for k in _VIN_KEYWORDS):
                r.score = 0.9
                validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# Dati catastali (foglio / particella / subalterno)
# ---------------------------------------------------------------------------
#
# Formato etichettato deterministico: "foglio 12 particella 345 sub 6",
# con abbreviazioni comuni (fg., part., mapp., sub.). Lo span copre
# l'intera sequenza etichette+numeri: sostituirla per intero è più
# sicuro che estrarre i soli numeri.

_CATASTO_REGEX = re.compile(
    r"(?i)"
    r"(?:foglio|fg\.?)\s*(?:n\.?\s*)?\d{1,5}"
    r"(?:\s*[,;]?\s*(?:particella|part\.?|mappale|mapp\.?)\s*(?:n\.?\s*)?\d{1,6})"
    r"(?:\s*[,;]?\s*(?:subalterno|sub\.?)\s*(?:n\.?\s*)?\d{1,4})?"
)


class CatastoRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="catasto", regex=_CATASTO_REGEX.pattern, score=0.9)
        ]
        super().__init__(
            supported_entity="IT_CATASTO",
            patterns=patterns,
            supported_language="it",
            context=["catasto", "catastale", "foglio", "particella"],
        )


# ---------------------------------------------------------------------------
# Numeri di pratica / protocollo / procedimento (keyword-gated)
# ---------------------------------------------------------------------------
#
# Copre gli identificativi amministrativi e giudiziari che seguono
# un'etichetta esplicita: R.G., sentenza, protocollo, pratica,
# repertorio/raccolta (atti notarili), fattura, polizza, matricola
# (INPS/aziendale/universitaria), posizione INAIL, iscrizione albo,
# verbale, codice identificativo contratto.
#
# Ogni pattern cattura in group(1) il SOLO identificativo: il testo
# resta leggibile ("sentenza n. «PRATICA_1»"). Il valore catturato
# deve contenere almeno una cifra (esclude "protocollo HTTPS").

# Ogni keyword ha un confine alfabetico a sinistra (``_B``): senza,
# "R.G." matcherebbe dentro "ORG" (falso positivo reale trovato sul
# report tecnico). La cattura termina sempre su un alfanumerico: mai
# consumare il punto di fine frase ("pratica n. 1234/2024." → cattura
# "1234/2024", non "1234/2024.").
_B = r"(?<![A-Za-z0-9])"
_ID_ALNUM = r"([A-Z0-9](?:[A-Z0-9./\-]{0,19}[A-Z0-9])?)"
_ID_NUM = r"(\d{1,6}(?:\s*/\s*\d{2,4})?)"

_PRATICA_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        _B + r"(?:n\.?\s*)?r\.?\s?g\.?\s*(?:n\.?|num\.?|nr\.?)?\s*:?\s*(\d{1,6}\s*/\s*\d{2,4}|\d{2,6})",
        _B + r"ruolo\s+generale\s*(?:n\.?|num\.?)?\s*:?\s*" + _ID_NUM,
        _B + r"sentenza\s*(?:n\.?|num\.?|nr\.?)?\s*:?\s*" + _ID_NUM,
        _B + r"decreto\s*(?:n\.?|num\.?)?\s*:?\s*" + _ID_NUM,
        _B + r"ordinanza\s*(?:n\.?|num\.?)?\s*:?\s*" + _ID_NUM,
        _B + r"prot(?:\.|ocollo)\s*(?:gen\.?|generale)?\s*(?:n\.?|num\.?|nr\.?)?\s*:?\s*" + _ID_ALNUM,
        _B + r"pratica\s*(?:n\.?|num\.?|nr\.?)?\s*:?\s*" + _ID_ALNUM,
        _B + r"rep(?:\.|ertorio)\s*(?:n\.?|num\.?)?\s*:?\s*(\d{1,7}(?:\s*/\s*\d{1,7})?)",
        _B + r"raccolta\s*(?:n\.?|num\.?)?\s*:?\s*(\d{1,7})",
        _B + r"fattura\s*(?:elettronica\s*)?(?:n\.?|num\.?|nr\.?)?\s*:?\s*" + _ID_ALNUM,
        _B + r"polizza\s*(?:n\.?|num\.?|nr\.?)?\s*:?\s*([A-Z0-9][A-Z0-9/\-]{1,18}[A-Z0-9])",
        _B + r"matricola\s*(?:inps|aziendale|universitaria)?\s*(?:n\.?|num\.?)?\s*:?\s*(\d{4,12})",
        _B + r"(?:posizione\s+)?inail\s*(?:n\.?|num\.?)?\s*:?\s*(\d{4,12})",
        _B + r"iscrizione\s+(?:all')?albo\s*(?:n\.?|num\.?)?\s*:?\s*([A-Z]{0,2}\d{2,8})",
        _B + r"verbale\s*(?:n\.?|num\.?)?\s*:?\s*" + _ID_NUM,
        _B + r"codice\s+(?:identificativo\s+)?(?:del\s+)?contratto\s*:?\s*([A-Z0-9]{6,20})",
    )
]


class PraticaRecognizer(EntityRecognizer):
    """Identificativi amministrativi/giudiziari con etichetta esplicita."""

    def __init__(self):
        super().__init__(
            supported_entities=["IT_PRATICA"],
            supported_language="it",
            name="PraticaRecognizer",
        )

    def load(self) -> None:  # pragma: no cover
        return None

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        results: list[RecognizerResult] = []
        visti: set = set()
        for rx in _PRATICA_PATTERNS:
            for m in rx.finditer(text):
                val = m.group(1)
                if not any(c.isdigit() for c in val):
                    continue
                span = (m.start(1), m.end(1))
                if span in visti:
                    continue
                visti.add(span)
                results.append(
                    RecognizerResult(
                        entity_type="IT_PRATICA",
                        start=span[0],
                        end=span[1],
                        score=0.9,
                    )
                )
        return results


# ---------------------------------------------------------------------------
# Handle social (@nome_utente)
# ---------------------------------------------------------------------------
#
# Il lookbehind esclude le email (nelle email la @ è preceduta da un
# carattere alfanumerico o punto). Escludiamo anche i match seguiti da
# un punto+TLD-like per non catturare metà di un'email malformata.

_SOCIAL_REGEX = re.compile(
    r"(?<![A-Za-z0-9_.@])"
    r"@[A-Za-z0-9_](?:[A-Za-z0-9_.]{1,28}[A-Za-z0-9_])?"
    r"(?![A-Za-z0-9_])"
)


class SocialHandleRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [Pattern(name="social", regex=_SOCIAL_REGEX.pattern, score=0.8)]
        super().__init__(
            supported_entity="IT_SOCIAL",
            patterns=patterns,
            supported_language="it",
            context=["instagram", "twitter", "telegram", "tiktok", "profilo"],
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        validated: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            # Scarta le forme "@ seguito da dominio" (resto di email).
            resto = text[r.end:r.end + 5]
            if resto.startswith(".") and len(resto) > 1 and resto[1].isalpha():
                continue
            if len(candidate) < 3:   # "@a" troppo corto
                continue
            # Terminazione TLD-like ("@iciuod.com", "@mocha.ni"):
            # frammenti di email spezzate (tipico dell'OCR), non handle.
            # Limite documentato: un handle vero che finisce con un
            # segmento di 2-3 lettere dopo un punto viene soppresso.
            if re.search(r"\.[A-Za-z]{2,3}$", candidate):
                continue
            r.score = 0.85
            validated.append(r)
        return validated


# ---------------------------------------------------------------------------
# Documento d'identità (pattern deterministici + keyword nel motore)
# ---------------------------------------------------------------------------
#
# Emette IT_DOCUMENTO su formati noti; il motore applica poi
# ``_documento_validato`` che richiede la keyword contestuale
# ("carta d'identità", "passaporto", "patente", "tessera sanitaria",
# "permesso di soggiorno"). Score alto: il vero filtro è la keyword.
#
#   CI cartacea:      AB 1234567
#   CIE elettronica:  CA00000AA
#   Passaporto:       AA1234567 (2 lettere + 7 cifre, come CI)
#   Patente:          AB1234567C (2 lettere + 7 cifre + 1 lettera) o
#                     U1B123456X (formati UE misti, coperti dal generico)
#   Tessera TEAM:     20 cifre (inizia con 80380 per l'Italia)

_DOC_PATTERNS_REGEX = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:"
    r"[A-Z]{2}[ \-]?\d{5}[ \-]?[A-Z]{2}"     # CIE CA 00000 AA
    r"|[A-Z]{2}[ \-]?\d{7}[A-Z]?"            # CI/passaporto/patente
    r"|803805\d{14}"                          # tessera TEAM italiana
    r")"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)


class DocumentoIdentitaRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="doc_identita", regex=_DOC_PATTERNS_REGEX.pattern, score=0.6)
        ]
        super().__init__(
            supported_entity="IT_DOCUMENTO",
            patterns=patterns,
            supported_language="it",
            context=["documento", "identità", "passaporto", "patente",
                     "tessera", "permesso"],
        )


# ---------------------------------------------------------------------------
# Organizzazioni con forma riconoscibile
# ---------------------------------------------------------------------------
#
# ORG era l'unica categoria affidata interamente al modello neurale, e
# l'audit (AUDIT_PRECISIONE.md § 6.1) ne ha misurato il costo: dei 46 span
# annotati, 22 esatti, 10 troncati al nucleo (``Studio Rosa & Associati``
# → ``Rosa`` come PERSONA) e 6 mancati — tutti e sei nomi tutti maiuscoli
# con forma societaria senza punti, che al modello non offrono appigli
# morfologici.
#
# Questi tre schemi non indovinano: leggono un marcatore esplicito.  Una
# forma societaria in coda, un ente in testa, o la formula dello studio
# associato.  Misurati sui documenti veri dell'utente producono 9 span su
# 247.000 caratteri, tutti e nove organizzazioni.
#
# Due vincoli imparati misurando, entrambi visibili negli schemi:
#
#   - separatori ``[ \t]`` e mai ``\s``: attraversare un a capo incolla la
#     fine di una riga all'inizio della successiva (``Confirmed: Two
#     Random`` ⏎ ``CHECKING UniCredit S.p.A.`` diventava un unico span), e
#     viola l'invariante di prodotto per cui nessuno span contiene ``\n``;
#   - ``Ordine`` solo con l'articolo: senza, ``N. Ordine Postel: 816213``
#     — un numero d'ordine — diventa un albo professionale.

_ORG_TITOLO = r"(?:Ing|Dott|Dr|Avv|Geom|Rag|Arch|Prof)\.[ \t]*"
_ORG_TOKEN = r"[A-ZÀ-Ù][\w'’\-]*\.?"

# Forma societaria in coda, con o senza punti: "Edilnord S.r.l.", "ICOS SRL".
_ORG_SUFFISSO_REGEX = re.compile(
    r"(?:(?<=\s)|(?<=^))"
    rf"(?:{_ORG_TITOLO})?"
    rf"(?:(?:{_ORG_TOKEN}|(?:&|e)[ \t]*)[ \t]*){{1,5}}"
    r"(?:S\.?[ \t]?r\.?[ \t]?l\.?s?|S\.?[ \t]?p\.?[ \t]?A\.?|S\.?[ \t]?n\.?[ \t]?c\.?"
    r"|S\.?[ \t]?a\.?[ \t]?s\.?|S\.?[ \t]?c\.?[ \t]?a\.?[ \t]?r\.?[ \t]?l\.?"
    r"|Soc\.?[ \t]?Coop\.?(?:[ \t]?a\.?[ \t]?r\.?[ \t]?l\.?)?"
    r"|S\.?[ \t]?S\.?[ \t]?D\.?|A\.?[ \t]?S\.?[ \t]?D\.?"
    r"|SRL|SPA|SNC|SAS|SCARL|Ltd\.?|LLC|GmbH|Inc\.?|Corp\.?|PLC)"
    r"(?![\w])"
)

# Ente in testa: "Comune di Cesenatico", "Procura della Repubblica di Perugia".
_ORG_PREFISSO_REGEX = re.compile(
    r"\b(?:Comune|Regione|Provincia|Città[ \t]+metropolitana"
    r"|Ordine[ \t]+(?:degli|dei|delle)|Collegio|Ministero|Agenzia|Tribunale"
    r"|Procura(?:[ \t]+della[ \t]+Repubblica)?|Questura|Prefettura"
    r"|Camera[ \t]+di[ \t]+Commercio|Istituto|Azienda|Ospedale|Universit[àa]"
    r"|Politecnico|Fondazione|Associazione|Cooperativa|Consorzio|Studio"
    r"|ASST|ASL|AUSL|ATS|INPS|INAIL|ARPA)"
    r"(?:[ \t]+(?:di|del|della|dei|degli|delle|d'))?"
    r"(?:[ \t]+[A-ZÀ-Ù][\w'’\-]*){1,3}"
    r"(?:[ \t]+(?:di|del|della|dei|degli|delle)[ \t]+[A-ZÀ-Ù][\w'’\-]*){0,2}"
    r"(?:[ \t]*&[ \t]*(?:Associati|Partners|Figli|Soci|C\.))?"
)

# Studio associato: "Bianchi & Partners", "Fumagalli & Figli".
_ORG_SOCI_REGEX = re.compile(
    rf"(?:(?<=\s)|(?<=^))(?:{_ORG_TITOLO})?{_ORG_TOKEN}"
    r"[ \t]*&[ \t]*(?:Associati|Partners|Figli|Soci)\b"
)

# Coda da non includere nello span: spazi, e la punteggiatura che l'OCR
# lascia a fine riga ("Procura della Repubblica di Perugia-").
_ORG_CODA = " \t-–,;:"


class OrganizzazioneRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="org_suffisso", regex=_ORG_SUFFISSO_REGEX.pattern, score=0.85),
            Pattern(name="org_prefisso", regex=_ORG_PREFISSO_REGEX.pattern, score=0.8),
            Pattern(name="org_soci", regex=_ORG_SOCI_REGEX.pattern, score=0.8),
        ]
        super().__init__(
            supported_entity="IT_ORGANIZZAZIONE",
            patterns=patterns,
            supported_language="it",
            context=["società", "ditta", "azienda", "impresa", "studio", "ente"],
            # Presidio compila i pattern con IGNORECASE per difetto. Qui
            # l'iniziale maiuscola È il segnale: senza questa riga
            # ``[A-ZÀ-Ù]`` accetta qualunque parola e lo span si allunga
            # all'indietro fino a cinque parole minuscole (misurato: span
            # esatti sul corpus da 43 a 8).
            global_regex_flags=re.DOTALL | re.MULTILINE,
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        tagliati: list[RecognizerResult] = []
        for r in results:
            fine = r.end
            while fine > r.start and text[fine - 1] in _ORG_CODA:
                fine -= 1
            if fine - r.start < 4:
                continue
            r.end = fine
            tagliati.append(r)
        return tagliati


# ---------------------------------------------------------------------------
# Sequenze con la forma di una carta che non superano Luhn
# ---------------------------------------------------------------------------
#
# Su documento scansionato il controllo di Luhn, che esiste per tenere alta
# la precisione, causa una fuga: l'OCR sbaglia una cifra, il checksum
# fallisce e il candidato viene scartato — proprio nel caso in cui il dato
# è più esposto.  Misurato su ``Indagine .pdf``: tre numeri di carta veri
# restano in chiaro nell'uscita perché sono varianti sfigurate di carte
# che il motore altrove maschera correttamente.
#
# Questi candidati NON vengono sostituiti: escono come suggerimento, con
# placeholder vuoto, e vanno spuntati a mano nel riquadro "Possibili
# entità".  Il percorso dei numeri che superano Luhn non cambia di una
# riga, quindi la precisione dei casi validi resta quella di prima.
#
# La condizione di contesto non è un di più.  Senza, entra anche
# ``Visitor 1D:6217•••••••••••••••``, che è un identificativo di sessione:
# una proposta sbagliata su quattro in un elenco di cui l'utente si deve
# fidare.  Con, sugli otto documenti veri escono quattro candidati, tutti
# e quattro numeri di carta.

_CARTA_SOSPETTA_REGEX = re.compile(r"(?<![\d.,\-/])(?:\d[ \-]?){12,18}\d(?![\d.,\-/])")

_CARTA_CONTESTO = re.compile(
    r"master\s?card|maestro|visa\b|amex|american\s?express"
    r"|carta\s+di\s+(?:credito|pagamento|debito)|n\.?\s?carta"
    r"|numero\s+(?:della\s+)?carta|credit\s?card|postepay|bancomat|\bPAN\b",
    re.IGNORECASE,
)

_CARTA_FINESTRA = 250


def _luhn_valido(cifre: str) -> bool:
    somma = 0
    for i, c in enumerate(reversed(cifre)):
        n = int(c)
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        somma += n
    return somma % 10 == 0


class CartaSospettaRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="carta_sospetta", regex=_CARTA_SOSPETTA_REGEX.pattern, score=0.35)
        ]
        super().__init__(
            supported_entity="IT_CARTA_SOSPETTA",
            patterns=patterns,
            supported_language="it",
            context=["carta", "credito", "pagamento"],
        )

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        tenuti: list[RecognizerResult] = []
        for r in results:
            cifre = re.sub(r"\D", "", text[r.start:r.end])
            if not 13 <= len(cifre) <= 19:
                continue
            if _luhn_valido(cifre):
                continue  # è una carta valida: la tratta il recognizer vero
            finestra = text[max(0, r.start - _CARTA_FINESTRA):r.end + _CARTA_FINESTRA]
            if not _CARTA_CONTESTO.search(finestra):
                continue
            tenuti.append(r)
        return tenuti


# ---------------------------------------------------------------------------
# Registrazione batch
# ---------------------------------------------------------------------------

def custom_italian_recognizers():
    """Restituisce l'elenco dei recognizer italiani custom."""
    recs = [
        CodiceFiscaleRecognizer(),
        PartitaIVARecognizer(),
        IBANItalianoRecognizer(),
        TelefonoItalianoRecognizer(),
        CAPItalianoRecognizer(),
        NomeCognomeRecognizer(),
        URLRecognizer(),
        IPRecognizer(),
        DataItalianaRecognizer(),
        DataNascitaRecognizer(),
        LuogoNascitaRecognizer(),
        IndirizzoItalianoRecognizer(),
        TargaItalianaRecognizer(),
        VINRecognizer(),
        CatastoRecognizer(),
        PraticaRecognizer(),
        SocialHandleRecognizer(),
        DocumentoIdentitaRecognizer(),
        OrganizzazioneRecognizer(),
        CartaSospettaRecognizer(),
    ]
    if not _NO_FIX3:
        recs.append(NumeroSpedizioneRecognizer())
    return recs
