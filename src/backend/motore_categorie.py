# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Categorie, tipi, placeholder e lingua — estratti da motore.py.

Questo modulo contiene le costanti e le funzioni che non dipendono dalla
pipeline di analisi: delimitatori placeholder, mappa tipi, priorità,
categorie opt-in, rilevamento lingua.  Tenute qui per non appesantire
motore.py (già 2200+ righe) e perché sono lette anche da api/main.py.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Delimitatori placeholder
# ---------------------------------------------------------------------------

_PH_OPEN = "«"   # U+00AB
_PH_CLOSE = "»"  # U+00BB
_PH_REGEX = re.compile(
    rf"{_PH_OPEN}([A-Z][A-Z_]*_\d+){_PH_CLOSE}"
)

# ---------------------------------------------------------------------------
# Soglie
# ---------------------------------------------------------------------------

_SOGLIA_ACCETTAZIONE = 0.4
_SOGLIA_PERSONA_CERTA = 0.7
_MAX_BLOCK = 25_000
_BATCH_THRESHOLD = 5_000

# ---------------------------------------------------------------------------
# Mappa tipi recognizer → placeholder
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[str, str] = {
    "PERSON": "PERSONA",
    "IT_NOME_COGNOME": "PERSONA",
    "IT_NOME_SUGGERITO": "PERSONA_SUGGERITO",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "TELEFONO",
    "IT_TELEFONO": "TELEFONO",
    "CREDIT_CARD": "CARTA",
    "IBAN_CODE": "IBAN",
    "IT_IBAN": "IBAN",
    "IT_CODICE_FISCALE": "CF",
    "IT_FISCAL_CODE": "CF",
    "IT_PARTITA_IVA": "PIVA",
    "IT_VAT_CODE": "PIVA",
    "IT_DRIVER_LICENSE": "DOCUMENTO",
    "IT_PASSPORT": "DOCUMENTO",
    "IT_IDENTITY_CARD": "DOCUMENTO",
    "IT_CAP": "CAP",
    "IT_INDIRIZZO": "INDIRIZZO",
    "IT_DATA_NASCITA": "DATA_NASCITA",
    "IT_LUOGO_NASCITA": "LUOGO_NASCITA",
    "LOCATION": "LUOGO",
    "GPE": "LUOGO",
    "ORGANIZATION": "ORG",
    "IT_ORGANIZZAZIONE": "ORG",
    "DATE_TIME": "DATA",
    "MEDICAL_LICENSE": "SANITARIO",
    "URL": "URL",
    "IP_ADDRESS": "IP",
    "IT_TARGA": "TARGA",
    "IT_IMPORTO": "IMPORTO",
    "IT_CATASTO": "CATASTO",
    "IT_DOCUMENTO": "DOCUMENTO",
    "IT_NUMERO_SPEDIZIONE": "SPEDIZIONE",
    "IT_VIN": "VIN",
    "IT_PRATICA": "PRATICA",
    "IT_SOCIAL": "SOCIAL",
    "MAC_ADDRESS": "MAC",
    "CRYPTO": "CRYPTO",
}

TIPI_ENTITA: list[str] = sorted(set(_TYPE_MAP.values()))

# ---------------------------------------------------------------------------
# Categorie opt-in
# ---------------------------------------------------------------------------

CATEGORIE_DEFAULT_ATTIVE: set[str] = {
    "PERSONA",
    "EMAIL",
    "TELEFONO",
    "IBAN",
    "CF",
    "PIVA",
    "CARTA",
    "CAP",
    "INDIRIZZO",
    "SANITARIO",
    "DOCUMENTO",
    "DATA_NASCITA",
    "LUOGO_NASCITA",
    "TARGA",
    "VIN",
    "PRATICA",
    "SOCIAL",
}

CATEGORIE_TUTTE: set[str] = set(TIPI_ENTITA) | {"PERSONA_SUGGERITO"}


def _tipo_di(entity_type: str) -> str:
    return _TYPE_MAP.get(entity_type, entity_type.upper())


# ---------------------------------------------------------------------------
# Priorità sovrapposizioni
# ---------------------------------------------------------------------------

_TYPE_PRIORITY: dict[str, int] = {
    "CF": 10,
    "PIVA": 9,
    "IBAN": 9,
    "CARTA": 8,
    "EMAIL": 8,
    "TELEFONO": 7,
    "PERSONA": 6,
    "LUOGO": 7,
    "INDIRIZZO": 8,
    "ORG": 4,
    "IT_ORGANIZZAZIONE": 8,
    "DATA": 9,
    "DATA_NASCITA": 10,
    "LUOGO_NASCITA": 10,
    "CAP": 2,
    "URL": 8,
    "IP": 8,
    "TARGA": 8,
    "IMPORTO": 5,
    "CATASTO": 8,
    "DOCUMENTO": 6,
    "SPEDIZIONE": 6,
    "VIN": 8,
    "PRATICA": 8,
    "SOCIAL": 8,
    "MAC": 8,
}

_PERSON_TYPES = {"PERSON", "PERSONA"}
_TIPI_SOLO_SUGGERITI = {"IT_NOME_SUGGERITO", "IT_CARTA_SOSPETTA"}
_TIPO_SUGGERIMENTO = {"IT_NOME_SUGGERITO": "PERSONA", "IT_CARTA_SOSPETTA": "CARTA"}

# ---------------------------------------------------------------------------
# Rilevamento lingua
# ---------------------------------------------------------------------------

_IT_HINT = re.compile(
    r"\b("
    r"il|lo|la|gli|le|un|una|uno|"
    r"di|da|del|della|dello|degli|delle|dei|dal|dalla|"
    r"in|su|sul|sulla|con|per|tra|fra|"
    r"e|ed|o|od|che|non|ma|se|come|"
    r"è|sono|siamo|siete|sei|era|erano|essere|"
    r"ha|hanno|abbiamo|avete|hai|aveva|avere|"
    r"sta|stanno|stiamo|stai|stava|stare|"
    r"fa|fanno|fatto|fare|"
    r"informiamo|confermiamo|comunichiamo|preghiamo|invitiamo|"
    r"prega|invita|conferma|informa|riscontro|allega|"
    r"signor|signora|signorina|sig|sig\.ra|dott|dott\.ssa|"
    r"nome|cognome|telefono|cellulare|email|posta|indirizzo|"
    r"via|corso|piazza|viale|largo|vicolo|"
    r"cliente|fornitore|societa|società|studio|azienda|ufficio|"
    r"fattura|contratto|preventivo|documento|colloquio|conferma|"
    r"cortese|gentile|distinti|cordiali|saluti"
    r")\b",
    re.IGNORECASE,
)

_IT_ACCENTS = re.compile(r"[àèéìíòóùúÀÈÉÌÍÒÓÙÚ]")


def _lingua(text: str) -> str:
    if _IT_ACCENTS.search(text):
        return "it"
    if _IT_HINT.search(text):
        return "it"
    if re.search(
        r"\b(the|and|of|to|is|are|was|were|for|with|from|by|this|that|"
        r"have|has|had|will|would|shall|should|please|dear|regards)\b",
        text, re.IGNORECASE,
    ):
        return "en"
    return "it"


# ---------------------------------------------------------------------------
# Categorie persistenti
# ---------------------------------------------------------------------------

def _leggi_categorie_attive() -> set[str]:
    from .aggiornamenti import _leggi_impostazioni

    cat = _leggi_impostazioni().get("categorie_attive")
    if isinstance(cat, list):
        return {c.upper() for c in cat if isinstance(c, str)}
    return set(CATEGORIE_DEFAULT_ATTIVE)


def scrivi_categorie_attive(categorie: set[str]) -> None:
    from .aggiornamenti import _leggi_impostazioni, _scrivi_impostazioni

    dati = _leggi_impostazioni()
    dati["categorie_attive"] = sorted({c.upper() for c in categorie})
    _scrivi_impostazioni(dati)
