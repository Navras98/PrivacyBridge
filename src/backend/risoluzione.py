# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Normalizzazione + risoluzione entità.

Regola non negoziabile: **la stessa forma letterale ha sempre lo
stesso segnaposto in tutta la sessione.** Forme diverse (anche della
stessa persona/azienda) hanno segnaposto distinti. Motivo:
`deanonimizza` è una tabella `segnaposto → valore` e un segnaposto
può puntare a un solo valore. Se fondiamo "Mario Rossi" e "Rossi"
sotto lo stesso «PERSONA_1», il ripristino trasforma il secondo in
"Mario Rossi" e il testo esce alterato — viola la garanzia G4.

Approccio: la lookup nel vault avviene sulla **chiave di risoluzione**
che, per tutti i tipi salvo DATA, è una normalizzazione **puramente
formale** che NON altera il testo ripristinato: NFC + strip +
compressione spazi + rimozione punteggiatura ai bordi. Preserva il
case e ogni token significativo (compresi titoli, forme societarie,
cognomi da soli, ecc.).

Ogni tipo:
  - PERSONA / ORG: `_base_norm`, senza rimozione onorifici né
    forme societarie. "Mario Rossi" ≠ "Rossi" ≠ "Dott. Mario Rossi".
    "Edilservice S.p.A." ≠ "Edilservice". "MARIO ROSSI" ≠ "Mario Rossi".
  - LUOGO / INDIRIZZO / CAP: `_base_norm`.
  - DATA: parse → canonical "YYYY-MM-DD" con "?" per parti mancanti.
    "19 giugno 2026" → "2026-06-19"; "giugno 2026" → "2026-06-??";
    "4 giugno" → "????-06-04". Chiavi diverse per parti diverse: mai
    unire "giugno 2026" (mese) con "19 giugno 2026" (giorno). Le date
    canonical sono deterministiche e il ripristino restituisce la
    forma letterale originale della prima occorrenza — invariante
    testuale garantita perché di norma la stessa data compare nello
    stesso formato all'interno di un documento.
  - Altro: `_base_norm`.

Compensazione: l'informazione "«PERSONA_2» è probabilmente la stessa
persona di «PERSONA_1»" non va perduta ma non deve toccare il testo.
Viene emessa nel campo `correlato_a` di ciascuna entità in output —
la UI la mostra in tabella (colonna dedicata) senza alterare il
comportamento dell'anonimizzazione.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Utility generiche
# ---------------------------------------------------------------------------

def _base_norm(v: str) -> str:
    """NFC + strip + rimozione punteggiatura ai bordi + compressione spazi.

    NON minuscolizza: "MARIO ROSSI" e "Mario Rossi" devono avere
    chiavi distinte, altrimenti al ripristino il case cambia.
    """
    if v is None:
        return ""
    s = unicodedata.normalize("NFC", str(v))
    s = s.strip()
    # Rimuovi punteggiatura ai bordi.
    s = re.sub(r"^[\s.,;:!?()\[\]{}\"'«»]+", "", s)
    s = re.sub(r"[\s.,;:!?()\[\]{}\"'«»]+$", "", s)
    # Comprimi spazi/tabs multipli.
    s = re.sub(r"\s+", " ", s)
    return s


# ---------------------------------------------------------------------------
# PERSONA / ORG / LUOGO — chiave = forma normalizzata (senza fusioni)
# ---------------------------------------------------------------------------

def chiave_persona(v: str) -> str:
    """Chiave letterale (normalizzata) per una persona.

    NON strippa titoli onorifici: "Dott. Mario Rossi" e "Mario Rossi"
    sono forme diverse → segnaposto distinti. Se serve segnalare la
    relazione si usa il campo ``correlato_a`` (vedi motore.py).
    """
    return _base_norm(v)


def chiave_org(v: str) -> str:
    """Chiave letterale (normalizzata) per un'organizzazione.

    NON strippa le forme societarie: "Edilservice S.p.A." e
    "Edilservice" sono forme diverse → segnaposto distinti.
    """
    return _base_norm(v)


def chiave_luogo(v: str) -> str:
    return _base_norm(v)


# ---------------------------------------------------------------------------
# DATA (canonical YYYY-MM-DD con ? per parti mancanti)
# ---------------------------------------------------------------------------

_MESI = {
    "gennaio": 1, "gen": 1, "01": 1, "1": 1,
    "febbraio": 2, "feb": 2, "02": 2, "2": 2,
    "marzo": 3, "mar": 3, "03": 3, "3": 3,
    "aprile": 4, "apr": 4, "04": 4, "4": 4,
    "maggio": 5, "mag": 5, "05": 5, "5": 5,
    "giugno": 6, "giu": 6, "06": 6, "6": 6,
    "luglio": 7, "lug": 7, "07": 7, "7": 7,
    "agosto": 8, "ago": 8, "08": 8, "8": 8,
    "settembre": 9, "set": 9, "sett": 9, "09": 9, "9": 9,
    "ottobre": 10, "ott": 10, "10": 10,
    "novembre": 11, "nov": 11, "11": 11,
    "dicembre": 12, "dic": 12, "12": 12,
}

# Pattern date supportati:
#  - "19/06/2026", "19-06-2026", "19.06.2026", "19/06/26"
#  - "2026-06-19"
#  - "19 giugno 2026", "giugno 2026", "4 giugno", "giugno"
_DATA_NUMERICA = re.compile(
    r"^\s*(\d{1,4})[/\-.](\d{1,2})(?:[/\-.](\d{1,4}))?\s*$"
)
_DATA_ISO = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$")
_DATA_TESTUALE = re.compile(
    r"^\s*(?:(\d{1,2})[\s°]?\s+)?"
    r"(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
    r"settembre|ottobre|novembre|dicembre|"
    r"gen|feb|mar|apr|mag|giu|lug|ago|set|sett|ott|nov|dic)"
    r"(?:\s+(\d{2,4}))?\s*$",
    re.IGNORECASE,
)


def chiave_data(v: str) -> str:
    """Ritorna la data canonica YYYY-MM-DD (con '?' per parti mancanti).

    Se ``v`` non è riconoscibile come data, ritorna la chiave generica.
    """
    s = _base_norm(v)
    if not s:
        return ""

    # 1. Formato ISO.
    m = _DATA_ISO.match(s)
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return f"{int(y):04d}-{mo:02d}-{d:02d}"

    # 2. Formato numerico con separatore.
    m = _DATA_NUMERICA.match(s)
    if m:
        a, b, c = m.group(1), m.group(2), m.group(3)
        if c is None:
            # DD/MM oppure MM/YYYY: ambiguo.
            if int(a) > 12:
                return f"????-{int(b):02d}-{int(a):02d}"
            if int(b) > 31:
                return f"{int(b):04d}-{int(a):02d}-??"
            # Ambigo: assumo giorno/mese
            return f"????-{int(b):02d}-{int(a):02d}"
        # DD/MM/YYYY (ordinamento italiano).
        d, mo, y = int(a), int(b), int(c)
        if y < 100:
            y = 2000 + y if y < 70 else 1900 + y
        return f"{y:04d}-{mo:02d}-{d:02d}"

    # 3. Formato testuale (mese in lettere).
    m = _DATA_TESTUALE.match(s)
    if m:
        d_str, mese_str, y_str = m.group(1), m.group(2), m.group(3)
        mo = _MESI.get(mese_str.lower(), None)
        if mo is None:
            return _base_norm(v)
        d = f"{int(d_str):02d}" if d_str else "??"
        y = None
        if y_str:
            y = int(y_str)
            if y < 100:
                y = 2000 + y if y < 70 else 1900 + y
        y_out = f"{y:04d}" if y else "????"
        return f"{y_out}-{mo:02d}-{d}"

    # Fallback: chiave generica.
    return s


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def chiave_di(valore: str, tipo: str) -> str:
    """Ritorna la chiave canonica per lookup nel vault, in base al tipo."""
    t = (tipo or "").upper()
    if t == "PERSONA":
        return chiave_persona(valore)
    if t == "ORG":
        return chiave_org(valore)
    if t in {"LUOGO", "INDIRIZZO", "CAP"}:
        return chiave_luogo(valore)
    if t == "DATA":
        return chiave_data(valore)
    return _base_norm(valore)


# ---------------------------------------------------------------------------
# Correlazioni fra segnaposto (compensazione informativa, non fusione)
# ---------------------------------------------------------------------------

# Onorifici e titoli comuni che, all'inizio di una forma persona,
# non contano per la relazione: "Dott. Mario Rossi" è correlato a
# "Mario Rossi". Elenco corto e volutamente italiano.
_ONORIFICI_LC = {
    "sig", "sig.", "sig.ra", "sig.na", "signor", "signora", "signorina",
    "dott", "dott.", "dott.ssa", "dott.sa", "dottor", "dottore",
    "dottoressa", "dr", "dr.",
    "ing", "ing.", "ingegner", "ingegnere",
    "arch", "arch.", "architetto",
    "avv", "avv.", "avvocato", "avvocata",
    "geom", "geom.", "geometra",
    "prof", "prof.", "professor", "professore", "professoressa",
    "rag", "rag.", "ragionier", "ragioniera",
    "egr", "egr.", "egregio", "egregia",
    "gentile", "gentilissimo", "gentilissima",
    "caro", "cara", "carissimo", "carissima",
    "il", "la", "lo", "i", "gli", "le",
    "un", "uno", "una",
    "cliente", "fornitore", "collega", "paziente",
}

_FORME_SOCIETARIE_LC = re.compile(
    r"\b(?:"
    r"s\.?\s*p\.?\s*a\.?"
    r"|s\.?\s*r\.?\s*l\.?s?"
    r"|s\.?\s*n\.?\s*c\.?"
    r"|s\.?\s*a\.?\s*s\.?"
    r"|s\.?\s*c\.?"
    r"|onlus|aps|odv|ets"
    r"|s\.?\s*coop\.?"
    r"|societa|società|impresa"
    r"|ltd|llc|inc|corp|gmbh|ag|plc"
    r")\b",
    re.IGNORECASE,
)


def _token_significativi_persona(v: str) -> list[str]:
    s = _base_norm(v).lower()
    return [t for t in (t.strip(".") for t in s.split())
            if t and t not in _ONORIFICI_LC]


def _token_significativi_org(v: str) -> list[str]:
    s = _FORME_SOCIETARIE_LC.sub(" ", _base_norm(v).lower())
    return [t for t in re.split(r"\s+|[&.,]+", s) if t]


def correlato_a(valore: str, tipo: str, esistenti: list[dict]) -> str | None:
    """Per un nuovo (``valore``, ``tipo``) e la lista di entità già
    emesse ``esistenti`` (dict con chiavi ``valore_reale``, ``tipo``,
    ``placeholder``), ritorna il placeholder correlato più probabile
    o ``None``. La correlazione è **puramente informativa**: non
    modifica placeholder né testo. La UI la mostra in tabella.

    Regola:
      - PERSONA: relazione se un token significativo di ``valore`` è
        un cognome (ultimo token) di un'altra persona esistente (o
        viceversa: un cognome che compare come ultimo token di
        un'altra forma più completa). Se l'ambiguità è multipla, None.
      - ORG: relazione se i token significativi di uno sono
        sottoinsieme dei token significativi dell'altro (in entrambi
        i sensi). Ambiguità multipla → None.
      - Altri tipi: None.
    """
    t = (tipo or "").upper()
    if not valore or not esistenti:
        return None

    if t == "PERSONA":
        toks = _token_significativi_persona(valore)
        if not toks:
            return None
        candidati = []
        for e in esistenti:
            if (e.get("tipo") or "").upper() != "PERSONA":
                continue
            e_toks = _token_significativi_persona(e.get("valore_reale") or "")
            if not e_toks or e_toks == toks:
                continue
            insieme_a = set(toks)
            insieme_b = set(e_toks)
            if insieme_a.issubset(insieme_b) or insieme_b.issubset(insieme_a):
                candidati.append(e["placeholder"])
        return candidati[0] if len(candidati) == 1 else None

    if t == "ORG":
        toks = _token_significativi_org(valore)
        if not toks:
            return None
        candidati = []
        for e in esistenti:
            if (e.get("tipo") or "").upper() != "ORG":
                continue
            e_toks = _token_significativi_org(e.get("valore_reale") or "")
            if not e_toks or e_toks == toks:
                continue
            insieme_a = set(toks)
            insieme_b = set(e_toks)
            if insieme_a.issubset(insieme_b) or insieme_b.issubset(insieme_a):
                candidati.append(e["placeholder"])
        return candidati[0] if len(candidati) == 1 else None

    return None
