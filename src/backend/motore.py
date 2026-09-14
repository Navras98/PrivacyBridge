# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Motore di anonimizzazione / de-anonimizzazione PrivacyBridge.

API pubblica:
    anonimizza(testo: str, sessione_id: str) -> tuple[str, list[dict]]
    deanonimizza(testo: str, sessione_id: str) -> tuple[str, dict]

Placeholder: ``«TIPO_N»`` (guillemets U+00AB / U+00BB).
Storage: SQLite (``backend/vault.py``, file ``data/vault.db`` di default).
"""

from __future__ import annotations

import logging
import re
import threading

from . import avanzamento
from .motore_categorie import (  # noqa: F401 — re-export per compatibilità esterna
    _BATCH_THRESHOLD,
    _MAX_BLOCK,
    _PERSON_TYPES,
    _PH_CLOSE,
    _PH_OPEN,
    _PH_REGEX,
    _SOGLIA_ACCETTAZIONE,
    _SOGLIA_PERSONA_CERTA,
    _TIPI_SOLO_SUGGERITI,
    _TIPO_SUGGERIMENTO,
    _TYPE_MAP,
    _TYPE_PRIORITY,
    _leggi_categorie_attive,
    _lingua,
    _tipo_di,
    CATEGORIE_DEFAULT_ATTIVE,
    CATEGORIE_TUTTE,
    TIPI_ENTITA,
    scrivi_categorie_attive,
)
from .risoluzione import chiave_di, correlato_a
from .truecasing import prevalentemente_minuscolo, ricapitalizza
from .vault import DEFAULT_DB_PATH, Vault

logger = logging.getLogger("privacybridge.motore")


# Particelle nobiliari / connettori italiani ammessi nei nomi propri.
_NAME_TOKENS_SET = {
    "De", "Del", "Della", "Delle", "Dello", "Degli", "Dei",
    "Di", "Da", "Dal", "Dalla", "Dalle", "Dallo", "Dagli",
    "La", "Lo", "Le", "Li", "Su",
    "Van", "Von", "Der", "D'", "D",
}


# Titoli onorifici/professionali: tollerati (e ignorati) ovunque nel match,
# altrimenti la forma minuscola ("dottor Hans Mueller") farebbe scartare
# l'intero nome.
_ONORIFICI = {
    "dottor", "dottore", "dottoressa", "dott", "dott.ssa", "dott.sa", "dr",
    "sig", "sig.ra", "sig.na", "signor", "signora", "signorina",
    "ing", "arch", "avv", "avvocato", "geom", "prof", "professor",
    "professore", "professoressa", "rag", "egr", "egregio", "gentile",
}


def _persona_valida(value: str, testo: str | None = None,
                    start: int | None = None) -> bool:
    """Filtro strutturale per stringhe che dichiarano di essere nomi di persona.

    Rifiuta match in cui una parola non-connettore inizia con minuscola
    (es. "Rossi ha firmato", "il contratto", "cliente Mario").

    Il dizionario nomi/cognomi ha priorità sulla grafia: un token in lista
    è strutturalmente valido anche minuscolo o tutto maiuscolo ("marco",
    "PASQUALE"). Lo span resta poi soggetto alla validazione semantica di
    ``_persona_validata_da_dizionario``, che è il vero cancello.

    Un singolo token è ammesso: il vecchio vincolo "2-4 token" scartava a
    monte ogni nome isolato ("Delfo", "PASQUALE", "marco") anche quando il
    NER lo aveva riconosciuto e il contesto era inequivocabile.

    Con ``testo``/``start`` valuta anche il contesto: dopo "sono", "mi
    chiamo" o un titolo, i token minuscoli fuori dizionario sono ammessi
    ("Ciao sono delfo berretti"). Resta poi la validazione semantica.
    """
    from .nomi_italiani import _cognome_noto, _nome_noto

    value = value.strip().strip(".,;:\"'()")
    if not value or len(value) > 60:
        return False
    tokens = value.split()
    if not (1 <= len(tokens) <= 4):
        return False
    contesto_forte = bool(
        testo is not None and start is not None
        and _TITOLI_PRE_PERSONA.search(testo[max(0, start - 40): start])
    )
    reali = 0
    for tok in tokens:
        clean = tok.strip(".,;:'\"()")
        if not clean:
            return False
        if clean.lower() in _ONORIFICI:
            continue
        if clean in _NAME_TOKENS_SET:
            continue
        reali += 1
        if not all(c.isalpha() or c in "'-" for c in clean):
            return False
        if clean[0].isupper() or contesto_forte:
            continue
        clean_lc = clean.lower()
        if not (_nome_noto(clean_lc) or _cognome_noto(clean_lc)):
            return False
    return reali > 0


# ---------------------------------------------------------------------------
# Filtro ruoli e uffici (non sono persone)
# ---------------------------------------------------------------------------
#
# Il modello neurale rizzo-pii tende a emettere come FULLNAME anche gli
# span che sono ruoli aziendali o nomi di ufficio: "Amministratore
# Delegato", "Direttore Finanziario", "Ufficio Crediti". Non sono dati
# personali e sostituirli rende il testo meno leggibile per l'assistente
# AI a valle. Li scartiamo esplicitamente dopo il post-filtro persona.

# Parole-chiave di RUOLO. Uno span PERSON che le contiene (case-insensitive)
# è probabilmente un ruolo, non un nome.
_RUOLI_PAROLE = {
    "amministratore", "amministratrice",
    "direttore", "direttrice", "direzione",
    "presidente", "vicepresidente", "vice-presidente",
    "consigliere", "consigliera",
    "responsabile",
    "coordinatore", "coordinatrice",
    "segretario", "segretaria",
    "tesoriere", "tesoriera",
    "revisore", "revisora",
    "capo", "vicecapo",
    "socio", "socia",
    "collaboratore", "collaboratrice",
    "delegato", "delegata",
    "referente",
    "manager",
}

# Parole-chiave di UFFICIO/ORGANO. Uno span PERSON che INIZIA con una di
# queste (case-insensitive) è quasi sempre un ente collettivo.
_UFFICI_PREFISSI = {
    "ufficio", "uffici",
    "servizio", "servizi",
    "consiglio",
    "comitato",
    "assemblea",
    "collegio",
    "direzione",
    "presidenza",
    "amministrazione",
    "segreteria",
    "commissione",
    "gruppo",
    "reparto",
    "sezione",
    "divisione",
    "unita", "unità",
    "team",
}


def _ruolo_o_ufficio(value: str) -> bool:
    """True se ``value`` è un ruolo aziendale o un nome di ufficio.

    Esempi che scartiamo:
      "Amministratore Delegato", "Direttore Finanziario",
      "Ufficio Crediti", "Consiglio di Amministrazione",
      "Comitato Investimenti", "Collegio Sindacale",
      "Assemblea Ordinaria".

    NON scartiamo se dopo la parola-ruolo c'è un cognome che identifica
    la persona ("Direttore Rossi" resta persona).
    """
    v = value.strip().strip(".,;:\"'()")
    if not v:
        return False
    tokens = [t.strip(".,;:'\"()") for t in v.split() if t.strip(".,;:'\"()")]
    if not tokens:
        return False
    tokens_lc = [t.lower() for t in tokens]

    # Ufficio/organo: se INIZIA con uno dei prefissi + qualcosa dopo.
    if tokens_lc[0] in _UFFICI_PREFISSI and len(tokens) >= 2:
        return True

    # Ruolo: se contiene una parola-ruolo E ha 2-4 token E gli altri
    # token sono qualificatori generici (aggettivi tipici di ruolo:
    # "Delegato", "Finanziario", "Generale", "Commerciale", ...) e
    # NON contiene un cognome noto (euristica: se tutti i token sono
    # ruoli/qualificatori, è ruolo puro; se un token è "Rossi" o
    # simile, è "Direttore Rossi" cioè persona).
    if any(t in _RUOLI_PAROLE for t in tokens_lc):
        qualificatori = {
            "delegato", "delegata",
            "generale", "generali",
            "finanziario", "finanziaria",
            "commerciale", "commerciali",
            "tecnico", "tecnica", "tecnici",
            "operativo", "operativa",
            "unico", "unica", "unici",
            "aggiunto", "aggiunta",
            "esecutivo", "esecutiva",
            "supplente", "supplenti",
            "ordinario", "ordinaria",
            "straordinario", "straordinaria",
            "amministrazione", "gestione", "vigilanza",
            "risorse", "umane", "personale",
            "vendite", "acquisti", "marketing",
            "produzione", "qualità", "qualita",
            "sistemi", "informativi", "informatici",
        }
        # Tutti i token sono ruoli o qualificatori (o preposizione/
        # articolo "di", "del", "della"): è un ruolo puro.
        connettori = {"di", "del", "della", "delle", "dello", "e", "ed", "al", "alla"}
        for t in tokens_lc:
            if t in _RUOLI_PAROLE or t in qualificatori or t in connettori:
                continue
            # Se il token è un titolo onorifico ("Dott.") ammesso.
            if t.rstrip(".") in _ONORIFICI:
                continue
            # Un token non-ruolo/qualificatore/connettore trovato:
            # probabilmente è il cognome della persona (es. "Direttore
            # Rossi"). NON scartiamo.
            return False
        return True

    return False


# _PERSON_TYPES, _TIPI_SOLO_SUGGERITI, _TIPO_SUGGERIMENTO,
# _TYPE_PRIORITY → motore_categorie.py (re-export sopra).


# ---------------------------------------------------------------------------
# Analyzer condiviso (lazy)
# ---------------------------------------------------------------------------

_analyzer = None
_analyzer_lock = threading.Lock()


def get_analyzer():
    """Restituisce l'AnalyzerEngine condiviso, caricato in modo pigro.

    Motore di default: neurale PII italiano (vedi ``backend.motore_neurale``).
    Override via variabile ambiente ``PRIVACYBRIDGE_MOTORE`` = "rizzo" |
    "none"; utile ai test veloci senza toccare il codice.
    Il modello resta su CPU: su questo hardware MPS è rotto (0 entità/OOM).

    ``nlp_engine`` è importato qui dentro e non in testa al modulo: tira
    dentro presidio, torch e spaCy, che da soli sono ~4s di import. In
    testa al modulo quei 4s li paga l'avvio dell'applicazione, dove
    l'utente guarda una finestra vuota; qui li paga la prima
    anonimizzazione, che stava già caricando il modello.
    """
    global _analyzer
    if _analyzer is None:
        with _analyzer_lock:
            if _analyzer is None:
                import os as _os

                from .nlp_engine import build_analyzer
                motore = _os.environ.get("PRIVACYBRIDGE_MOTORE", "rizzo")
                _analyzer = build_analyzer(motore=motore)
    return _analyzer


def reset_analyzer() -> None:
    """Forza la ricostruzione dell'analyzer al prossimo uso (utile nei test)."""
    global _analyzer
    with _analyzer_lock:
        _analyzer = None


# _IT_HINT, _IT_ACCENTS, _lingua → motore_categorie.py (re-export sopra).


# ---------------------------------------------------------------------------
# Filtraggio sovrapposizioni
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# BUG-real 2: validazione dizionario per span NER
# ---------------------------------------------------------------------------

# Contesti che precedono uno span PERSONA e ne giustificano
# l'accettazione anche per token single-word:
#  - titoli (Sig., Dott., Ing., ...)
#  - formule di apertura (Gentile, Ciao, Buongiorno, ...)
#  - verbi di presentazione (sono, mi chiamo, ...)
_TITOLI_PRE_PERSONA = re.compile(
    r"(?i)\b(?:"
    r"sig(?:nor|nora|norina|\.?ra|\.?na|\.?)|"
    r"dott(?:or|ore|oressa|\.?ssa|\.?sa|\.?)|dr\.?|"
    r"ing(?:egner|egnere|\.?)|arch(?:itetto|\.?)|"
    r"avv(?:ocato|ocata|\.?)|geom(?:etra|\.?)|"
    r"prof(?:essor|essore|essoressa|\.?)|"
    r"rag(?:ionier|ioniera|\.?)|"
    r"on(?:orevole|\.?)|"
    r"gentile|gentilissim[oa]|egregi[oa]|carissim[oa]|caro|cara|"
    r"spett\.?le|spettabile|"
    # Campi etichettati di modulo ("Nome: Mario", "Cognome: Rossi").
    r"nome|cognome|nominativo|intestatario|richiedente|dichiarante|"
    r"referente|beneficiario|assistito|"
    # Formule di apertura + verbi di presentazione (per il pass
    # single-token del filtro validazione).
    r"buongiorno|buonasera|salve|ciao|"
    r"sono|mi\s+chiamo|scrivo\s+io|vi\s+scrivo|ti\s+scrivo|"
    r"il\s+cliente|la\s+cliente|il\s+fornitore|il\s+paziente|"
    r"parla|risposta\s+da|da\s+parte\s+di|"
    # Formule di chiusura/firma (con virgola opzionale + newline).
    r"cordiali\s+saluti|distinti\s+saluti|un\s+saluto|"
    r"cordialmente|saluti|grazie|a\s+presto"
    r")\s*[.:,]?\s*\n?\s*[-—]?\s*$"
)


def _persona_validata_da_dizionario(
    span_txt: str, testo: str, start: int,
    valore_originale: str | None = None,
    da_neurale: bool = False,
) -> bool:
    """True se lo span PERSONA soddisfa almeno una condizione:

    Single-token:
      - Se è un **nome di battesimo NOTO e NON ambiguo** nel dizionario
        italiano (es. "Giacomo", "Giuseppe", "Matteo"), è **sempre
        valido**: sono nomi propri che non coincidono con parole comuni
        italiane, quindi non c'è dubbio.
      - Altrimenti richiede TITOLO esplicito prima ("signor", "dott.",
        "ing."), oppure è ambiguo (Rosa, Serena, Grazia — parole comuni)
        e viene scartato.

    Multi-token (es. "Mario Rossi", "Marco Rossi"): il PRIMO token
    deve essere in dizionario nomi/cognomi — la sequenza multi-token
    è indicativa di persona.

    Sempre valido: preceduto da titolo inequivocabile.
    """
    from .nomi_italiani import (
        _COGN_TUTTI,
        _NOMI_TUTTI,
        _VOCAB_IT,
        _VOCAB_IT_ESTESO,
        _e_inizio_frase,
        _nome_ambiguo,
        _nome_noto,
    )
    tokens = [
        t for t in re.split(r"[\s.,'\-()]+", span_txt.strip())
        if t and len(t) >= 2
    ]
    if not tokens:
        return False

    # Titolo/contesto esplicito prima: vale anche per i nomi FUORI
    # dizionario ("Ciao sono Delfo"). Finestra allargata a 40 char per
    # catturare "Cordiali saluti,\n" (17 char) + nome.
    finestra = testo[max(0, start - 40): start]
    if _TITOLI_PRE_PERSONA.search(finestra):
        # Guardia: il contesto forte non deve trasformare in persona una
        # parola comune ("sono felice", "sono andato", "sono le otto").
        # Il dizionario vince sul vocabolario: "berretti" è un cognome
        # anche se è pure il plurale di "berretto".
        for t in tokens:
            t_lc = t.lower()
            if _nome_noto(t_lc) or t_lc in _COGN_TUTTI:
                return True
        from .filtri_rumore import _in_blacklist_tecnica
        for t in tokens:
            t_lc = t.lower()
            if t_lc in _VOCAB_IT or t.isdigit() or _in_blacklist_tecnica(t):
                return False
        return True

    if len(tokens) == 1:
        tok_lc = tokens[0].lower()
        # Nome di stato o continente isolato: senza l'innesco personale
        # verificato sopra è geografia, non una persona. Il dizionario
        # italiano contiene "Italia", "Francia", "India", "Asia" come
        # nome o cognome, e su documenti reali questo produceva persone
        # inesistenti ("in Francia, Guatemala o India?").
        from .filtri_rumore import e_paese_o_macroarea
        if e_paese_o_macroarea(tok_lc):
            return False
        # Livello 1 del sistema a tre livelli: nome noto NON ambiguo
        # → sempre valido, senza contesto. Un cognome noto NON ambiguo
        # da solo (Ferrari) resta soggetto alla vecchia regola: il
        # recognizer nomi_italiani non lo emette da solo (livello 3
        # come suggerimento). Il rizzo NER può emetterlo: lì
        # richiediamo titolo per evitare "Ferrari" (marchio auto).
        if _nome_noto(tok_lc) and not _nome_ambiguo(tok_lc):
            # Eccezione: bigrammi tecnici in blacklist (es. "Monte
            # Carlo" = metodo statistico, non persona). Controllo la
            # parola immediatamente precedente.
            from .filtri_rumore import _in_blacklist_tecnica
            finestra_pre = testo[max(0, start - 30): start]
            m_prec = re.search(r"(\b\w+)\s+$", finestra_pre)
            if m_prec:
                bigramma = f"{m_prec.group(1)} {span_txt.strip()}"
                if _in_blacklist_tecnica(bigramma):
                    return False
            # Guardia "capitale sintetica" (classe FP trovata dalla
            # suite avversariale: "la vittoria della squadra", "dora
            # l'arrosto", "la scuola romana"). Se nel testo ORIGINALE
            # il token era minuscolo, la maiuscola è del truecasing —
            # e per i nomi che collidono con parole comuni (vocab
            # esteso 660k) o con toponimi (lista comuni: Vittoria,
            # Romana) serve un trigger sintattico personale, non basta
            # il livello 1.
            #
            # Non vale per gli span del NER neurale: il modello legge la
            # frase intera e decide da sé. Misurato: emette PERSON su
            # "marco"/"maria" in "sono con giovanni, marco e maria" e su
            # nessuno dei controcasi ("io marco le presenze", "dora
            # l'arrosto", "la vittoria della squadra", "una rosa rossa").
            # La guardia serve al recognizer a dizionario, che match-a
            # alla cieca; applicarla al neurale ne buttava il giudizio.
            if valore_originale is not None and not da_neurale and \
                    valore_originale.strip()[:1].islower():
                from .truecasing import _COMUNI
                if (tok_lc in _VOCAB_IT or tok_lc in _VOCAB_IT_ESTESO
                        or tok_lc in _COMUNI):
                    from .nomi_italiani import _TRIGGER_NOME_MINUSCOLO
                    fin = testo[max(0, start - 30): start]
                    m_trig = None
                    for m_trig in _TRIGGER_NOME_MINUSCOLO.finditer(fin):
                        pass
                    if not (m_trig and m_trig.end() >= len(fin)):
                        return False
            # Guardia inizio-frase per nomi del seed che coincidono con
            # parola comune ("Vittoria schiacciante", "Fiore
            # all'occhiello", "Aurora boreale"). L'inizio-frase
            # maiuscolizza qualunque parola: senza altro contesto
            # personale non si distingue nome dall'uso comune.
            if tok_lc in _VOCAB_IT and _e_inizio_frase(testo, start):
                end = start + len(span_txt)
                j = end
                while j < len(testo) and testo[j] in " \t":
                    j += 1
                k = j
                while k < len(testo) and (testo[k].isalpha() or testo[k] == "'"):
                    k += 1
                prox_raw = testo[j:k].lower()
                # Se contiene apostrofo (preposizioni articolate,
                # elisioni), prendo il prefisso prima dell'apostrofo:
                # "all'occhiello" → "all" (che è preposizione articolata
                # → uso comune, non nome).
                prefisso = prox_raw.split("'", 1)[0]
                if prefisso in {"all", "dell", "sull", "dall", "nell",
                                "un", "d", "l"}:
                    return False
                prox = prox_raw.rstrip("'")
                if (
                    prox
                    and (prox in _VOCAB_IT or prox in _VOCAB_IT_ESTESO)
                    and prox not in _NOMI_TUTTI
                    and prox not in _COGN_TUTTI
                ):
                    return False
            return True
        # Altrimenti: single-token ambiguo o non-nome → richiede
        # titolo esplicito (già verificato sopra).
        return False

    # Multi-token: il PRIMO token deve essere nel dizionario nomi/
    # cognomi. Un nome vero comincia con un nome vero: "Mario Rossi",
    # "Marco Rossi", "Anna della Valle" iniziano tutti con nome noto.
    # "qui la caccia", "di terzi", "Disclosure del parziale" no.
    primo_lc = tokens[0].lower()
    return primo_lc in _NOMI_TUTTI or primo_lc in _COGN_TUTTI


# Città estere note che potrebbero comparire in "residente a X" o
# "nato a X" senza essere in comuni ISTAT. Elenco piccolo e curato.
_CITTA_ESTERE = {
    "londra", "london", "parigi", "paris", "berlino", "berlin",
    "madrid", "barcellona", "barcelona", "lisbona", "lisboa",
    "amsterdam", "bruxelles", "brussels", "vienna", "wien",
    "praga", "prague", "budapest", "varsavia", "warsaw",
    "atene", "athens", "istanbul", "mosca", "moscow", "san pietroburgo",
    "new york", "los angeles", "san francisco", "chicago", "boston",
    "washington", "toronto", "montreal", "vancouver",
    "città del messico", "buenos aires", "san paolo", "rio de janeiro",
    "il cairo", "cape town", "johannesburg", "casablanca",
    "dubai", "abu dhabi", "riyadh", "tel aviv", "gerusalemme",
    "pechino", "beijing", "shanghai", "tokyo", "seoul", "singapore",
    "bangkok", "hong kong", "mumbai", "delhi", "kolkata",
    "sidney", "sydney", "melbourne", "auckland",
    "malta", "la valletta", "san marino",
}


def _luogo_validato(span_txt: str, testo: str, start: int) -> bool:
    """True se il toponimo di LUOGO_NASCITA è validato:
      1. È un comune italiano noto (lista ISTAT).
      2. È una città estera nota.
      3. È preceduto da campo etichettato esplicito ("luogo di
         nascita:", "comune di nascita:", ecc.) — in quel caso il
         valore lo determina l'utente.
    """
    from .truecasing import _COMUNI, _COMUNI_TOKENS
    val = span_txt.strip().lower()
    if not val:
        return False
    if val in _COMUNI or val in _CITTA_ESTERE:
        return True
    # Toponimo multi-parola: verifica se il primo token è un
    # capoluogo/comune noto (es. "Reggio Emilia" ha "Reggio" in
    # COMUNI_TOKENS).  Meno affidabile ma copre Reggio Emilia,
    # San Giovanni Valdarno, ecc.
    parti = val.split()
    if parti and parti[0] in _COMUNI_TOKENS:
        return True
    # Campo etichettato esplicito: cerca "luogo di nascita:" ecc. nei
    # 30 caratteri precedenti.
    finestra = testo[max(0, start - 30): start].lower()
    return any(k in finestra for k in (
        "luogo di nascita", "comune di nascita",
        "provincia di nascita", "paese di nascita",
    ))


# Formati plausibili documento identità italiano.
#   CI cartacea:      AB 1234567 (2 lettere + 7 cifre)
#   CI elettronica:   CA00000AA  (2 lettere + 5 cifre + 2 lettere)
#   Passaporto nuovo: YA1234567  (1 lettera + 7 cifre) — alcuni formati
#   Passaporto vecchio (fino 2005): 1234567 (7 cifre) + lettera
_DOC_ID_FORMATO = re.compile(
    r"^(?:"
    r"[A-Z]{2}[\s\-]?[0-9]{7}"                       # CI cartacea
    r"|[A-Z]{2}[\s\-]?[0-9]{5}[\s\-]?[A-Z]{2}"       # CIE elettronica
    r"|[A-Z][A-Z0-9]{5,9}"                           # generico documento alfanumerico
    r"|803805\d{14}"                                 # tessera sanitaria TEAM
    r")$",
    re.IGNORECASE,
)

_DOC_KEYWORDS = (
    "documento", "docum.", "doc.",
    "carta d'identità", "carta di identità", "carta identità",
    "cie", "c.i.e.", "c.i.",
    "passaporto", "passport",
    "patente",
    "tessera sanitaria", "team", "tessera",
    "permesso di soggiorno",
    "n. doc", "n° doc",
)


_TEL_IT_STRINGENTE = re.compile(
    r"^"
    r"(?:"
    r"(?:\+39|0039)[\s\-]?[0-9](?:[\s\-]?[0-9]){7,10}"
    r"|3[0-9]{2}[\s\-]?[0-9]{3}[\s\-]?[0-9]{3,4}"
    r"|0[0-9]{1,3}[\s\-]?[0-9]{5,8}"
    r")"
    r"$"
)


def _targa_validata(span_txt: str, testo: str, start: int) -> bool:
    """Validazione deterministica per gli span TARGA di QUALSIASI
    origine (in particolare il neurale, che emette IT_TARGA anche su
    'AZ 610' — numero di volo). Formato auto moderno completo, oppure
    formato parziale + keyword veicolare nelle vicinanze.
    """
    from .recognizers import _TARGA_KEYWORDS, _TARGA_LETTERE
    compatto = re.sub(r"[ \-]", "", span_txt).upper()
    if re.fullmatch(rf"[{_TARGA_LETTERE}]{{2}}\d{{3}}[{_TARGA_LETTERE}]{{2}}",
                    compatto):
        return True
    if not (any(c.isdigit() for c in compatto)
            and any(c.isalpha() for c in compatto)):
        return False
    lo = max(0, start - 40)
    hi = min(len(testo), start + len(span_txt) + 20)
    ctx = testo[lo:hi].lower()
    return any(k in ctx for k in _TARGA_KEYWORDS)


def _telefono_validato(span_txt: str) -> bool:
    """True se lo span corrisponde a un vero telefono italiano.
    Applicato a tipi TELEFONO emessi dal presidio standard, che
    catturano anche anni (1689) e metriche (0.987 0.990)."""
    v = span_txt.strip()
    # Nessun separatore decimale.
    if "," in v or "." in v:
        return False
    return bool(_TEL_IT_STRINGENTE.match(v))


def _documento_validato(span_txt: str, testo: str, start: int) -> bool:
    """True se lo span DOCUMENTO ha formato plausibile E c'è una
    parola chiave contestuale nelle vicinanze.

    Restrittivo per default perché il neurale rizzo emette DOCID su
    qualsiasi numero ("748", "1234/2024", "~67.8 M").
    """
    val = span_txt.strip()
    if not _DOC_ID_FORMATO.match(val):
        return False
    finestra = testo[max(0, start - 40): min(len(testo), start + len(val) + 10)].lower()
    return any(k in finestra for k in _DOC_KEYWORDS)


def _tronca_span_su_newline(results: list, testo: str) -> list:
    """Nessuno span può contenere ``\\n`` o ``\\r``. Se un match li
    attraversa (PDF con tabelle multi-colonna letti come frasi
    continue), viene troncato al primo a capo. Se il pezzo residuo è
    troppo corto o solo whitespace, viene scartato.
    """
    out = []
    for r in results:
        span_text = testo[r.start:r.end]
        idx = min(
            [span_text.find(c) for c in "\n\r" if c in span_text] or [-1]
        )
        if idx == -1:
            out.append(r)
            continue
        new_end = r.start + idx
        # Rifila whitespace finale.
        while new_end > r.start and testo[new_end - 1] in " \t":
            new_end -= 1
        if new_end - r.start < 2:
            continue   # troppo corto, scarta
        out.append(type(r)(
            entity_type=r.entity_type,
            start=r.start,
            end=new_end,
            score=r.score,
        ))
    return out


# Punteggiatura che non fa mai parte di un nome di persona, né in testa
# né in coda. Il NER la include quando il nome chiude la frase ("marco!",
# "Rossi,"): lo span sporco poi non supera i filtri strutturali.
_BORDI_DA_RIFILARE = " \t!?.,;:«»\"'()[]…"


def _rifila_bordi_persona(results: list, testo: str) -> list:
    """Toglie la punteggiatura ai bordi degli span di persona.

    Classe di difetto: "andrò da, marco!" produce lo span "marco!", che
    veniva scartato perché contiene un carattere non alfabetico — il nome
    spariva per colpa del punto esclamativo.
    """
    out = []
    for r in results:
        if r.entity_type not in _PERSON_TYPES and \
                r.entity_type != "IT_NOME_COGNOME":
            out.append(r)
            continue
        inizio, fine = r.start, r.end
        while inizio < fine and testo[inizio] in _BORDI_DA_RIFILARE:
            inizio += 1
        while fine > inizio and testo[fine - 1] in _BORDI_DA_RIFILARE:
            fine -= 1
        if fine - inizio < 2:
            continue
        if (inizio, fine) == (r.start, r.end):
            out.append(r)
            continue
        out.append(type(r)(
            entity_type=r.entity_type,
            start=inizio, end=fine, score=r.score,
        ))
    return out


# Parole che al bordo di uno span PERSONA sono SEMPRE fuori posto: sono
# i verbi e i participi che il neurale ingloba quando la frase descrive
# lo stato anagrafico della persona ("Matteo Rossi nato a Roma").
# Sono anche gli **indicatori di contesto** che i recognizer
# LUOGO_NASCITA e DATA_NASCITA usano per innescarsi: se restano dentro
# la PERSONA, un innesco è sepolto dentro lo span del vicino.
_PAROLE_CONTESTO_ANAGRAFICO = frozenset({
    "nato", "nata", "nate", "nati", "nasce", "nascere",
    "residente", "residenti",
    "domiciliato", "domiciliata",
    "originario", "originaria",
    "coniugato", "coniugata", "sposato", "sposata",
    "detto", "detta", "chiamato", "chiamata",
    "presso",
    # ausiliari e verbi di stato comuni immediatamente dopo un nome
    "ha", "hanno", "è", "era", "erano", "sono", "sei",
    "sarà", "sarebbe",
})

# Preposizioni/articoli/congiunzioni monosillabici che non possono far
# parte di un nome di persona italiana. Tenuti separati da
# _PAROLE_CONTESTO_ANAGRAFICO perché la logica di appartenenza è diversa
# (queste sono classi chiuse della grammatica, quelle sono forme
# lessicali).
_FUNZIONALI_MAI_NEL_NOME = frozenset({
    "a", "ad", "in", "il", "lo", "la", "le", "gli", "l'",
    "un", "una", "uno", "un'",
    "di", "da", "del", "della", "delle", "dei", "degli", "dal", "dalla",
    "con", "per", "su", "fra", "tra", "senza", "verso",
    "che", "e", "o", "ma", "come",
})


def _e_scarto_bordo_persona(token: str) -> bool:
    """True se ``token`` al bordo di uno span PERSONA è chiaramente NON
    parte di un nome di persona.

    Classe di difetto (2026-08-02): il neurale emette "Matteo Rossi nato"
    come PERSON; la parola "nato" finisce dentro la persona e sparisce
    dall'uscita, e lo stesso "nato" è l'indicatore usato dal recognizer
    LUOGO_NASCITA per innescarsi su "Assisi" — un indicatore di contesto
    non può stare dentro lo span di un'altra entità.

    Regola pratica:
    - se è una parola del contesto anagrafico (`nato`, `residente`,
      `domiciliato`, ausiliari, …) → SCARTO;
    - se è un funzionale (preposizione, articolo, congiunzione) → SCARTO;
    - se è nome o cognome noto (anche ambiguo) → tienilo, altrimenti
      "Rossi", "Bianchi", "Verdi" sparirebbero perché sono anche parole
      comuni;
    - se è un onorifico o una particella nobiliare → tienilo;
    - se contiene cifre → scarto;
    - altrimenti (sconosciuto: potrebbe essere un nome straniero come
      "Delfo" o "Mueller") → tienilo.
    """
    from .nomi_italiani import _COGN_TUTTI, _NOMI_TUTTI
    t = token.strip(".,;:!?«»\"'()[]…").lower()
    if not t:
        return True
    if any(c.isdigit() for c in t):
        return True
    if t in _PAROLE_CONTESTO_ANAGRAFICO:
        return True
    if t in _FUNZIONALI_MAI_NEL_NOME:
        return True
    if t in _NOMI_TUTTI or t in _COGN_TUTTI:
        return False
    if t.rstrip(".") in _ONORIFICI:
        return False
    if t in _PARTICELLE_MERGE:
        return False
    return False


def _pota_span_persona_da_contesto(results: list, testo: str) -> list:
    """Rimuove dai bordi degli span PERSONA i token che sono parole
    funzionali/verbi/preposizioni.

    Il neurale, su frasi come "Matteo Rossi nato a Roma", tende a
    inglobare il participio nello span PERSON ("Matteo Rossi nato"). Se
    quello span venisse sostituito così com'è, la parola "nato" sparirebbe
    dall'uscita; il downstream perderebbe il contesto anagrafico e — cosa
    peggiore — lo stesso "nato" è la parola che il recognizer
    LUOGO_NASCITA usa per innescarsi su "Assisi". Un indicatore di
    contesto non può stare **dentro** lo span di un'altra entità.

    Pota da testa e coda ricorsivamente finché il token al bordo è uno
    scarto (vedi ``_e_scarto_bordo_persona``). Se lo span si svuota, scarta
    l'entità.
    """
    if not results:
        return results
    out = []
    for r in results:
        if r.entity_type not in _PERSON_TYPES and \
                r.entity_type != "IT_NOME_COGNOME":
            out.append(r)
            continue
        # Trova le posizioni assolute dei token dentro [r.start, r.end).
        span_txt = testo[r.start:r.end]
        tokens = [
            (m.start() + r.start, m.end() + r.start, m.group(0))
            for m in re.finditer(r"\S+", span_txt)
        ]
        if not tokens:
            continue
        # Pota la coda.
        while tokens and _e_scarto_bordo_persona(tokens[-1][2]):
            tokens.pop()
        # Pota la testa.
        while tokens and _e_scarto_bordo_persona(tokens[0][2]):
            tokens.pop(0)
        if not tokens:
            # Span svuotato: nulla di sostanziale dentro. Scarta.
            continue
        nuovo_start = tokens[0][0]
        nuovo_end = tokens[-1][1]
        if (nuovo_start, nuovo_end) == (r.start, r.end):
            out.append(r)
            continue
        out.append(type(r)(
            entity_type=r.entity_type,
            start=nuovo_start, end=nuovo_end, score=r.score,
        ))
    return out


_PARTICELLE_MERGE = {
    "de", "di", "da", "del", "dello", "della", "delle", "degli", "dei",
    "dal", "dalla", "dallo", "dalle", "dagli", "dai",
    "lo", "la", "le", "li",
    "d'", "l'", "dell'", "nell'",
    "van", "von", "der",
}


def _fondi_persone_con_particelle(results: list, testo: str) -> list:
    """Fonde span PERSONA adiacenti separati solo da whitespace +
    particella nobiliare + whitespace. Copre casi come "Serena Di
    Giovanni" che il neurale emette come due PERSON separati.
    """
    if not results:
        return results
    person_indices = [
        i for i, r in enumerate(results)
        if _tipo_di(r.entity_type) == "PERSONA"
    ]
    if len(person_indices) < 2:
        return results
    # Ordinati per start.
    person_indices.sort(key=lambda i: results[i].start)
    fusi = set()
    nuovi: list = []
    for idx_ord, i in enumerate(person_indices):
        if i in fusi:
            continue
        r = results[i]
        # Cerca un successivo PERSONA vicino con particella in mezzo.
        j = idx_ord + 1
        cur_end = r.end
        while j < len(person_indices):
            k = person_indices[j]
            r2 = results[k]
            if r2.start <= cur_end:
                j += 1
                continue
            gap = testo[cur_end: r2.start]
            gap_stripped = gap.strip()
            if gap_stripped.lower() in _PARTICELLE_MERGE:
                # Fondi: estendi r fino a r2.
                fusi.add(k)
                cur_end = r2.end
                j += 1
                continue
            break
        if cur_end != r.end:
            r = type(r)(
                entity_type=r.entity_type,
                start=r.start,
                end=cur_end,
                score=r.score,
            )
        nuovi.append(r)
    # Aggiungi gli span NON-persona invariati.
    for i, r in enumerate(results):
        if _tipo_di(r.entity_type) != "PERSONA":
            nuovi.append(r)
    return nuovi


def _scarta_luogo_su_nome_certo(results: list, testo: str) -> list:
    """Elimina i LOCATION/GPE del NER neurale quando esattamente lo stesso
    span è riconosciuto anche come ``IT_NOME_COGNOME`` a livello 1
    (nome noto NON ambiguo del dizionario).

    Motivazione: il modello neurale marca come LOCATION qualsiasi token
    dopo "da"/"a"/"in" ("sono passato da Grazia", "vado da Marco"). La
    priorità LUOGO=7 > PERSONA=6 esiste per non spezzare gli odonimi
    ("Corso Vittorio Emanuele"), ma su span singolo che è un nome di
    battesimo notorio non ambiguo (Grazia, Marco, Aurora, Chiara...) il
    verdetto persona è certo.
    """
    if not results:
        return results
    from .nomi_italiani import _nome_ambiguo, _nome_noto
    # Indici degli IT_NOME_COGNOME single-token affidabili: nome noto
    # non ambiguo, punteggio da _SOGLIA_PERSONA_CERTA in su.
    span_persona_certi: set[tuple[int, int]] = set()
    for r in results:
        if r.entity_type != "IT_NOME_COGNOME":
            continue
        if r.score < _SOGLIA_PERSONA_CERTA:
            continue
        val = testo[r.start:r.end].strip()
        if not val or " " in val:
            continue
        vl = val.lower()
        if _nome_noto(vl) and not _nome_ambiguo(vl):
            span_persona_certi.add((r.start, r.end))
    if not span_persona_certi:
        return results
    out: list = []
    for r in results:
        if (r.entity_type in {"LOCATION", "GPE", "IT_LUOGO_NASCITA"}
                and (r.start, r.end) in span_persona_certi):
            continue
        out.append(r)
    return out


def _propaga_cognomi_confermati(spans: list, testo: str) -> list:
    """Fix 1b (2026-07-31, richiesta dal gate finale): se una persona
    multi-token è confermata ("Mario Rossi"), le occorrenze isolate e
    capitalizzate del suo cognome ("Rossi conferma l'ordine") altrove
    nel testo diventano PERSONA — con segnaposto DISTINTO (chiave =
    forma letterale) e correlazione in tabella.

    Guardie anti-FP: match case-sensitive sulla forma esatta del
    cognome come appare nella persona confermata; niente overlap con
    span esistenti; token ≥ 3 caratteri; mai onorifici.
    """
    if not spans:
        return spans
    confermati: set[str] = set()
    for sp in spans:
        if _tipo_di(sp.entity_type) != "PERSONA":
            continue
        toks = testo[sp.start:sp.end].split()
        if len(toks) < 2:
            continue
        ultimo = toks[-1].strip(".,;:'\"()")
        if (len(ultimo) >= 3 and ultimo[0].isupper()
                and ultimo.lower() not in _ONORIFICI):
            confermati.add(ultimo)
    if not confermati:
        return spans
    occupati = [(s.start, s.end) for s in spans]

    def _libero(a: int, b: int) -> bool:
        return all(b <= s or e <= a for s, e in occupati)

    from presidio_analyzer import RecognizerResult
    nuovi = list(spans)
    for cognome in confermati:
        for m in re.finditer(
            rf"(?<![\wÀ-ÿ]){re.escape(cognome)}(?![\wÀ-ÿ])", testo
        ):
            if not _libero(m.start(), m.end()):
                continue
            nuovi.append(RecognizerResult(
                entity_type="IT_NOME_COGNOME",
                start=m.start(), end=m.end(), score=0.8,
            ))
            occupati.append((m.start(), m.end()))
    return nuovi


# Un'enumerazione è una sequenza di parole singole legate da virgola e/o
# da una congiunzione: "marco, giovanni, maria, luisa e fiorella",
# "luca, o PASQUALE". Il legame ammesso fra due elementi contigui.
_LEGAME_ENUM = {",", "e", "ed", "o", "od", ", e", ", ed", ", o", ", od"}

_ELEMENTO_ENUM = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']*")

# Lunghezza massima di un elemento di enumerazione trattato come nome.
_MAX_LEN_ELEMENTO_ENUM = 20


def _propaga_nomi_in_enumerazione(spans: list, testo: str) -> list:
    """Fix C: in un'enumerazione di nomi, se ALMENO UNO è già confermato
    gli altri elementi presenti nel dizionario nomi/cognomi diventano
    PERSONA.

    "sono con marco, giovanni, maria, luisa e fiorella": giovanni, luisa
    e fiorella sono certi → marco e maria sono confermati dalla lista.
    L'informazione è già nel testo e non costa un modello in più.

    Guardie anti-FP: l'ancora dev'essere una PERSONA che copre esattamente
    un elemento; l'elemento promosso dev'essere in dizionario, non una
    formula esclusa, non sovrapposto ad altri span.
    """
    if not spans:
        return spans
    from .nomi_italiani import (
        _FORMULE_ESCLUSE,
        _VOCAB_IT,
        _cognome_noto,
        _nome_ambiguo,
        _nome_noto,
    )

    def _plausibile_nome(parola_lc: str) -> bool:
        """Un elemento di enumerazione degno di promozione.

        Un nome di battesimo basta anche se coincide con una parola
        comune ("marco" è pure una voce del verbo marcare): in una lista
        di persone la collisione non è più ambigua. Un COGNOME che è
        anche parola comune ("penso", "casa", "porto", "credo") no: da
        solo produrrebbe falsi positivi su qualunque elenco di verbi.
        """
        if _nome_ambiguo(parola_lc):
            return False
        if _nome_noto(parola_lc):
            return True
        return _cognome_noto(parola_lc) and parola_lc not in _VOCAB_IT

    elementi: list[tuple[int, int, str]] = []
    for m in _ELEMENTO_ENUM.finditer(testo):
        parola = m.group(0)
        if parola.lower() in {"e", "ed", "o", "od"}:
            continue
        elementi.append((m.start(), m.end(), parola))
    if len(elementi) < 2:
        return spans

    ancore = {
        (sp.start, sp.end) for sp in spans
        if _tipo_di(sp.entity_type) == "PERSONA"
    }
    occupati = [(sp.start, sp.end) for sp in spans]

    def _libero(a: int, b: int) -> bool:
        return all(b <= s or e <= a for s, e in occupati)

    # Raggruppo gli elementi contigui legati da virgola/congiunzione.
    gruppi: list[list[int]] = []
    corrente = [0]
    for i in range(1, len(elementi)):
        legame = " ".join(testo[elementi[i - 1][1]:elementi[i][0]].split())
        if legame in _LEGAME_ENUM:
            corrente.append(i)
        else:
            gruppi.append(corrente)
            corrente = [i]
    gruppi.append(corrente)

    from presidio_analyzer import RecognizerResult

    from .filtri_rumore import e_rumore
    nuovi = list(spans)
    for gruppo in gruppi:
        if len(gruppo) < 2:
            continue
        if not any((elementi[i][0], elementi[i][1]) in ancore for i in gruppo):
            continue
        for i in gruppo:
            inizio, fine, parola = elementi[i]
            if (inizio, fine) in ancore or not _libero(inizio, fine):
                continue
            parola_lc = parola.lower()
            if (len(parola) > _MAX_LEN_ELEMENTO_ENUM
                    or parola_lc in _FORMULE_ESCLUSE
                    or not _plausibile_nome(parola_lc)
                    or e_rumore(parola, "PERSON")):
                continue
            nuovi.append(RecognizerResult(
                entity_type="IT_NOME_COGNOME",
                start=inizio, end=fine, score=0.8,
            ))
            occupati.append((inizio, fine))
    return nuovi


# Un nome ripetuto è in posizione di lista o di vocativo se è seguito da
# punteggiatura: "con marco, sto andando", "andrò da, marco!". Un verbo
# omografo regge invece un complemento ("io marco le presenze", "marco a
# matita le correzioni"), quindi è seguito da una parola.
_DOPO_NOME_RIPETUTO = set(",;!?:)")

# ...e dev'essere introdotto da una preposizione di compagnia. Senza
# questo vincolo la regola promuoveva "fonte", "IVA" e "Francia" nei
# documenti reali: ricorrono, stanno in frasi con persone confermate e
# sono seguiti da punteggiatura, ma nessuno scrive "con IVA," o "da
# fonte,". Le preposizioni puramente locative ("in Francia") sono fuori.
_PRIMA_NOME_RIPETUTO = re.compile(
    r"(?i)\b(?:con|da|insieme\s+a|assieme\s+a|in\s+compagnia\s+di)\s*,?\s*$"
)


def _propaga_nomi_ripetuti(spans: list, testo: str) -> list:
    """Coreferenza intra-documento per i nomi di battesimo ricorrenti.

    Se un nome proprio compare più volte nello stesso testo, quel testo
    contiene già almeno una persona confermata, e almeno una occorrenza è
    in posizione di lista o vocativo, allora tutte le occorrenze sono la
    stessa persona.

    Serve ai nomi che collidono con una voce verbale ("marco") e che per
    questo il truecasing non ricapitalizza e i modelli non vedono. Le
    guardie escludono l'uso verbale: "io marco le presenze" ha una sola
    occorrenza, nessuna persona confermata e nessuna occorrenza seguita
    da punteggiatura.
    """
    if not spans:
        return spans
    from .nomi_italiani import (
        _NOMI_ESCLUSI_PASS_MINUSCOLO,
        _nome_ambiguo,
        _nome_noto,
    )

    if not any(_tipo_di(sp.entity_type) == "PERSONA" for sp in spans):
        return spans
    occupati = [(sp.start, sp.end) for sp in spans]

    def _libero(a: int, b: int) -> bool:
        return all(b <= s or e <= a for s, e in occupati)

    posizioni: dict[str, list[tuple[int, int]]] = {}
    for m in _ELEMENTO_ENUM.finditer(testo):
        parola_lc = m.group(0).lower()
        if (not _nome_noto(parola_lc) or _nome_ambiguo(parola_lc)
                or parola_lc in _NOMI_ESCLUSI_PASS_MINUSCOLO):
            continue
        posizioni.setdefault(parola_lc, []).append((m.start(), m.end()))

    from presidio_analyzer import RecognizerResult
    nuovi = list(spans)
    from .filtri_rumore import e_rumore
    for parola_lc, occorrenze in posizioni.items():
        if len(occorrenze) < 2:
            continue
        in_lista = any(
            (fine >= len(testo) or testo[fine] in _DOPO_NOME_RIPETUTO)
            and _PRIMA_NOME_RIPETUTO.search(testo[max(0, inizio - 30): inizio])
            for inizio, fine in occorrenze
        )
        if not in_lista or e_rumore(testo[occorrenze[0][0]:occorrenze[0][1]],
                                    "PERSON"):
            continue
        for inizio, fine in occorrenze:
            if not _libero(inizio, fine):
                continue
            nuovi.append(RecognizerResult(
                entity_type="IT_NOME_COGNOME",
                start=inizio, end=fine, score=0.8,
            ))
            occupati.append((inizio, fine))
    return nuovi


def _risolvi_sovrapposizioni(results: list) -> list:
    """Rimuove risultati sovrapposti tenendo il migliore.

    Regole:
      1. Se A è contenuto in B (span), tiene quello con priorità di tipo
         più alta; a parità, quello più lungo; a parità, score più alto.
      2. Se A e B si sovrappongono parzialmente, applica le stesse regole.
    """
    if not results:
        return results
    # Ordino per (start, -length): prima gli span più ampi che iniziano prima.
    results = sorted(results, key=lambda r: (r.start, -(r.end - r.start)))

    def _score(r) -> tuple:
        tipo = _tipo_di(r.entity_type)
        # Prima l'``entity_type`` grezzo: permette a un recognizer
        # deterministico di avere precedenza diversa dal modello neurale
        # che produce lo stesso tipo finale.
        base = _TYPE_PRIORITY.get(r.entity_type, _TYPE_PRIORITY.get(tipo, 5))
        priority = base
        # Il match perfetto (score == 1.0) tipico della RUBRICA:
        # priorità assoluta sopra ogni altro recognizer. Uso il
        # confronto ESATTO (non >= 0.99) per non catturare anche
        # DATE_TIME che il presidio standard può emettere con 1.0.
        if r.score == 1.0 and tipo not in {
            "DATA", "DATA_NASCITA", "LUOGO", "LUOGO_NASCITA", "INDIRIZZO",
        }:
            priority = 100
        # ``base`` e il nome del tipo in coda rendono l'ordine TOTALE.
        # Senza, due recognizer che tornano entrambi 1.0 sullo stesso span
        # producevano tuple identiche e vinceva quello che l'analyzer
        # aveva restituito per primo — un ordine che cambia da un processo
        # all'altro. Misurato: "P.IVA 12345678901" (undici cifre: per una
        # società il codice fiscale È la partita IVA, e i due recognizer
        # rispondono tutti e due con 1.0) usciva «PIVA_1» o «CF_2» a
        # esecuzioni alterne sullo stesso testo. Il dato era mascherato in
        # entrambi i casi, ma il tipo mostrato in tabella ballava e ogni
        # confronto prima/dopo ereditava quel rumore.
        return (priority, r.end - r.start, r.score, base, r.entity_type)

    tenuti: list = []
    for r in results:
        conflitto_idx = None
        for i, t in enumerate(tenuti):
            if r.start < t.end and t.start < r.end:
                conflitto_idx = i
                break
        if conflitto_idx is None:
            tenuti.append(r)
            continue
        if _score(r) > _score(tenuti[conflitto_idx]):
            tenuti[conflitto_idx] = r
    return tenuti


# ---------------------------------------------------------------------------
# Blocchi per testi lunghi (usato solo nella fase di sostituzione R→L)
# ---------------------------------------------------------------------------

def _split_blocchi(testo: str, size: int = _MAX_BLOCK) -> list[tuple[int, str]]:
    """Divide il testo in blocchi non più lunghi di ``size`` caratteri.

    Preferisce spezzare su un a-capo vicino al limite: per l'invariante
    di prodotto NESSUNO span attraversa un ``\\n`` (BUG-real 1), quindi
    il taglio su newline non può spezzare un'entità. In mancanza di
    newline ripiega sull'ultimo spazio. Ritorna (offset, blocco).
    """
    if len(testo) <= size:
        return [(0, testo)]
    blocchi = []
    i = 0
    n = len(testo)
    while i < n:
        j = min(i + size, n)
        if j < n:
            k = testo.rfind("\n", max(i, j - 2000), j)
            if k <= i:
                k = testo.rfind(" ", max(i, j - 500), j)
            if k > i:
                j = k
        blocchi.append((i, testo[i:j]))
        i = j
    return blocchi


def _analizza_a_blocchi(analyzer, testo: str, lang: str) -> list:
    """Analisi PII a blocchi per i testi lunghi.

    Su testi molto lunghi l'analisi monolitica degrada in modo
    NON lineare (misurato: 100k → 1.900 char/s; 389k → ~300 char/s)
    e gonfia la memoria (documento spaCy unico). A blocchi da
    ``_MAX_BLOCK`` il costo torna quasi lineare e il picco RSS resta al
    livello del singolo blocco. Gli offset dei risultati vengono
    riportati sul testo completo.

    Effetto di bordo accettato: le finestre di contesto (~40 char)
    dei recognizer non attraversano il confine di blocco; il taglio
    avviene su un a-capo, dove il contesto è comunque interrotto.
    """
    if len(testo) <= _MAX_BLOCK:
        return list(analyzer.analyze(text=testo, language=lang,
                                     score_threshold=0.0))
    risultati: list = []
    for offset, blocco in _split_blocchi(testo, _MAX_BLOCK):
        for r in analyzer.analyze(text=blocco, language=lang,
                                  score_threshold=0.0):
            r.start += offset
            r.end += offset
            risultati.append(r)
        # Il blocco è la grana dell'avanzamento mostrato: qui i caratteri
        # sono analizzati sul serio, non stimati.
        avanzamento.segna(offset + len(blocco))
    return risultati


# ---------------------------------------------------------------------------
# API PUBBLICA
# ---------------------------------------------------------------------------

# _leggi_categorie_attive / scrivi_categorie_attive → motore_categorie.py
# (re-export sopra, l'API pubblica di motore.py resta identica).


def anonimizza(
    testo: str,
    sessione_id: str,
    *,
    vault: Vault | None = None,
    db_path: str | None = None,
    lingua: str | None = None,
    categorie_attive: set[str] | None = None,
    diagnosi: bool = False,
) -> tuple[str, list[dict]]:
    """Anonimizza ``testo`` per la sessione ``sessione_id``.

    Ritorna ``(testo_anonimizzato, lista_entita)`` dove ogni entità è un dict
    con chiavi ``placeholder``, ``valore_reale``, ``tipo``, ``occorrenze``.

    Con ``diagnosi=True`` (o ``PRIVACYBRIDGE_DIAGNOSI=1``) traccia il
    percorso di ogni candidato — vedi ``backend.diagnosi``.
    """

    if testo is None:
        return "", []
    if not isinstance(testo, str):
        raise TypeError("testo deve essere una stringa")

    from .diagnosi import Tracer, attiva_da_env, registra
    trace = Tracer(diagnosi or attiva_da_env())

    own_vault = False
    if vault is None:
        use_batch = len(testo) > _BATCH_THRESHOLD
        vault = Vault(db_path or DEFAULT_DB_PATH, batch_mode=use_batch)
        own_vault = True
        if use_batch:
            # In batch_mode le lookup vanno alla cache, non a SQLite: senza
            # preload i contatori ripartirebbero da 1 e riassegnerebbero
            # placeholder già emessi a valori diversi.
            vault.preload_session(sessione_id)

    avanzamento.inizia(len(testo))
    try:
        lang = lingua or _lingua(testo)
        analyzer = get_analyzer()

        # Categorie attive: parametro esplicito > impostazioni persistenti > default.
        cat_attive = (
            {c.upper() for c in categorie_attive}
            if categorie_attive is not None
            else _leggi_categorie_attive()
        )

        # Termini in rubrica (case-insensitive): passano sempre il filtro
        # categoria — sono l'esplicita volontà dell'utente.
        try:
            from .rubrica import _leggi_termini_rubrica  # type: ignore
            _rubrica_lc = _leggi_termini_rubrica()
        except Exception:
            _rubrica_lc = set()

        # 1. TRUECASING (fix strutturale): se il testo è prevalentemente
        #    minuscolo, ricapitalizziamo con lookup nel dizionario nomi/
        #    cognomi/comuni prima di passarlo all'analyzer.  Preserva la
        #    lunghezza → gli offset degli span coincidono col testo
        #    originale, che continueremo a usare per la sostituzione.
        testo_analisi = testo
        if prevalentemente_minuscolo(testo):
            testo_analisi, _ = ricapitalizza(testo)
            trace.ev("truecasing", "testo prevalentemente minuscolo → "
                     "ricapitalizzato prima dell'analisi")

        # 2. Analisi PII (a blocchi sopra _MAX_BLOCK caratteri).
        #    score_threshold=0.0 così i "suggerimenti" del dizionario nomi
        #    (livello 3, score 0.35, tipo IT_NOME_SUGGERITO) arrivano
        #    qui: li separiamo poi dagli hit attivi.
        results = _analizza_a_blocchi(analyzer, testo_analisi, lang)

        if trace.attiva:
            for r in results:
                meta = getattr(r, "recognition_metadata", None) or {}
                origine = meta.get("recognizer_name", "sconosciuto")
                trace.candidato(r, testo_analisi, origine)
            trace.analizza_token_persi(
                testo_analisi, {(r.start, r.end) for r in results}
            )

        # BUG-real 1: nessuno span può attraversare un a capo.
        # Nei PDF con tabelle, righe di colonne diverse finiscono
        # adiacenti e il motore le legge come frase continua ("Andrea
        # Rossi\nProgetto", "Deterministico\nLayout"). Se un match
        # contiene \n o \r, tronchiamo al primo a capo.
        pre = list(results)
        results = _tronca_span_su_newline(results, testo_analisi)
        if trace.attiva and len(results) != len(pre):
            spans_dopo = {(r.start, r.end) for r in results}
            for r in pre:
                if (r.start, r.end) not in spans_dopo:
                    trace.scartato(r, testo_analisi, "newline",
                                   "span attraversava un a capo")

        # Pre-filtro: quando il neurale emette LOCATION su un token che è
        # anche riconosciuto come persona certa dal dizionario, scarta il
        # LOCATION (il suo punteggio 0.95 vincerebbe la priorità LUOGO>PERSONA
        # e cancellerebbe la persona).
        results = _rifila_bordi_persona(results, testo_analisi)

        # Pota dai bordi degli span PERSONA i token che sono parole
        # funzionali/verbi/preposizioni (nato, residente, ad, il, …).
        # Corregge il difetto per cui il neurale inglobava "nato" in
        # "Matteo Rossi nato a Roma" e la parola spariva dall'uscita.
        results = _pota_span_persona_da_contesto(results, testo_analisi)

        pre = list(results)
        results = _scarta_luogo_su_nome_certo(results, testo_analisi)
        if trace.attiva and len(results) != len(pre):
            rimasti = set(map(id, results))
            for r in pre:
                if id(r) not in rimasti:
                    trace.scartato(r, testo_analisi, "luogo-su-nome-certo",
                                   "stesso span è un nome noto non ambiguo")

        span_globali = []
        span_suggeriti = []
        # Ordine dei passi (rivisto 2026-07-31):
        #  1. Pre-filtro STRUTTURALE (persona_valida, spazzatura,
        #     score minimo) + CATEGORIA.
        #  2. Filtri di VALIDAZIONE (dizionario persona, luogo,
        #     documento, telefono, targa, rumore).
        #  3. SOLO ALLA FINE la risoluzione sovrapposizioni.
        # Motivo (classe di bug trovata dalla suite avversariale): uno
        # span destinato a morire (categoria disattiva o validazione
        # fallita) NON deve prima vincere la sovrapposizione contro
        # uno span valido — si porterebbe via il dato sottostante
        # (LOCATION spento che mangiava IT_TELEFONO; IT_LUOGO_NASCITA
        # non-validato che mangiava IT_INDIRIZZO).
        candidati_full: list = []
        for r in results:
            if r.entity_type in _TIPI_SOLO_SUGGERITI:
                span_suggeriti.append(r)
                continue
            if r.entity_type in {"MISC", "NORP", "MONEY", "PERCENT",
                                 "QUANTITY", "ORDINAL", "CARDINAL", "EVENT",
                                 "WORK_OF_ART", "LAW", "LANGUAGE", "FAC",
                                 "PRODUCT", "TIME", "JOB_TITLE"}:
                trace.scartato(r, testo_analisi, "tipo-escluso",
                               f"tipo {r.entity_type} mai anonimizzato")
                continue
            if r.score < _SOGLIA_ACCETTAZIONE:
                trace.scartato(r, testo_analisi, "score",
                               f"score {r.score:.2f} < {_SOGLIA_ACCETTAZIONE}")
                continue
            # Passo 1 — struttura persona (solo su PERSON del NER,
            # non su IT_NOME_COGNOME che è a livello token).
            if r.entity_type in _PERSON_TYPES and not _persona_valida(
                testo_analisi[r.start:r.end], testo_analisi, r.start
            ):
                trace.scartato(r, testo_analisi, "persona-struttura",
                               "2-4 token con iniziali maiuscole richiesti")
                continue
            # Passo 1b — filtro CATEGORIA prima delle sovrapposizioni.
            # Uno span di categoria disattiva non deve competere: se
            # vincesse la sovrapposizione e poi venisse filtrato, si
            # porterebbe via il dato sottostante (classe di bug reale:
            # LOCATION spento che "mangiava" IT_TELEFONO/IT_INDIRIZZO
            # e il valore restava in chiaro).
            tipo_out = _tipo_di(r.entity_type)
            if (tipo_out not in cat_attive
                    and testo[r.start:r.end].strip().lower() not in _rubrica_lc):
                trace.scartato(r, testo_analisi, "categoria",
                               f"categoria {tipo_out} disattiva")
                continue
            candidati_full.append(r)

        # Passo 2 — filtri di validazione (PRIMA delle sovrapposizioni).
        for r in candidati_full:

            valore_span = testo[r.start:r.end]
            # Per i filtri uso testo_analisi (truecased) — sul testo
            # originale minuscolo alcuni check non scatterebbero.
            valore_analisi = testo_analisi[r.start:r.end]
            valore_lc = valore_span.strip().lower()

            # La rubrica sovrascrive TUTTI i filtri (compresa la
            # validazione dizionario). Un termine esplicitamente
            # inserito in rubrica dall'utente deve essere sostituito.
            in_rubrica = valore_lc in _rubrica_lc

            if not in_rubrica:
                # (persona_valida struttura già applicata al passo 1)
                # Filtro ruoli/uffici: PERSONA da qualsiasi source.
                if _tipo_di(r.entity_type) == "PERSONA":
                    if _ruolo_o_ufficio(valore_analisi):
                        trace.scartato(r, testo_analisi, "ruolo-ufficio",
                                       "è un ruolo aziendale o un ufficio")
                        continue
                    # BUG-real 2: validazione dizionario per tutti gli
                    # span PERSONA (sia NER che nostro recognizer).
                    # Single-token: richiede contesto forte prima
                    # (titolo, formula apertura, verbo di presentazione).
                    # Multi-token: almeno un token in dizionario.
                    _meta = getattr(r, "recognition_metadata", None) or {}
                    if not _persona_validata_da_dizionario(
                        valore_analisi, testo_analisi, r.start,
                        valore_originale=valore_span,
                        da_neurale=(
                            _meta.get("recognizer_name") == "NeuralRecognizer"
                        ),
                    ):
                        trace.scartato(r, testo_analisi, "dizionario-persona",
                                       "non validato dal dizionario nomi "
                                       "(ambiguo senza titolo, o primo token "
                                       "non in lista)")
                        continue

                # BUG-real 2: LUOGO_NASCITA — toponimo in comuni
                # italiani o preceduto da campo etichettato.
                if _tipo_di(r.entity_type) == "LUOGO_NASCITA" and not _luogo_validato(
                    valore_analisi, testo_analisi, r.start
                ):
                    trace.scartato(r, testo_analisi, "luogo-validato",
                                   "non è comune ISTAT/città estera nota "
                                   "né campo etichettato")
                    continue

                # BUG-real 3c: DOCUMENTO — formato plausibile CI/
                # passaporto italiano E keyword contestuale.
                if _tipo_di(r.entity_type) == "DOCUMENTO" and not _documento_validato(
                    valore_analisi, testo_analisi, r.start
                ):
                    trace.scartato(r, testo_analisi, "documento-validato",
                                   "formato non plausibile o keyword "
                                   "documento assente nelle vicinanze")
                    continue

                # BUG-real 3b: TELEFONO — presidio standard emette
                # PHONE_NUMBER anche su "1689" (anno) e "0.987 0.990"
                # (metriche). Se non passa la mia regex italiana
                # stringente, scarto.
                if (_tipo_di(r.entity_type) == "TELEFONO"
                        and not _telefono_validato(valore_analisi)):
                    trace.scartato(r, testo_analisi, "telefono-validato",
                                   "non rispetta il formato telefono "
                                   "italiano stringente")
                    continue

                # TARGA (dal neurale): formato targa vero o keyword.
                if (_tipo_di(r.entity_type) == "TARGA"
                        and not _targa_validata(valore_analisi, testo_analisi, r.start)):
                    trace.scartato(r, testo_analisi, "targa-validata",
                                   "non è formato targa né c'è keyword "
                                   "veicolare vicina")
                    continue

                # Filtri anti-rumore B2+B3 (titoli maiuscoli, nomi
                # file, snake_case, codici brevi, marchi pubblici).
                # Non applichiamo alle entità con validatore aritmetico.
                if r.entity_type not in {
                    "IT_CODICE_FISCALE", "IT_FISCAL_CODE",
                    "IT_PARTITA_IVA", "IT_VAT_CODE",
                    "IT_IBAN", "IBAN_CODE",
                    "CREDIT_CARD",
                    "EMAIL_ADDRESS",
                    # Deterministici con validatore di formato/keyword:
                    # sono per natura "tutto maiuscolo" o alfanumerici
                    # (targa, VIN, documento) e il filtro anti-rumore
                    # li ucciderebbe.
                    "IT_TARGA", "IT_VIN", "IT_CATASTO", "IT_PRATICA",
                    "IT_SOCIAL", "IT_DOCUMENTO", "MAC_ADDRESS", "CRYPTO",
                    # Una ragione sociale è tutta maiuscola sulle fatture e
                    # nelle intestazioni: "ICOS SRL", "UNICREDIT SPA",
                    # "BETA IMMOBILIARE SPA" finivano tutte e tre nella
                    # regola "titolo in MAIUSCOLO" (AUDIT_PRECISIONE.md
                    # § 6.1). Lo span deterministico è già vincolato a una
                    # forma giuridica o a un prefisso istituzionale, quindi
                    # non porta il rumore che quella regola intercetta.
                    # Vale solo per il recognizer deterministico: l'ORG
                    # neurale ("ORGANIZATION") continua a passare dal filtro.
                    "IT_ORGANIZZAZIONE",
                }:
                    from .filtri_rumore import e_rumore
                    if e_rumore(valore_analisi, r.entity_type):
                        trace.scartato(r, testo_analisi, "rumore",
                                       "filtro B2/B3 (maiuscolo, file, "
                                       "codice, marchio, parola comune)")
                        continue

            # (Il filtro categoria è applicato al passo 1b.)
            span_globali.append(r)

        # Passo 3 — risoluzione sovrapposizioni sugli span validati.
        pre = list(span_globali)
        span_obj = _risolvi_sovrapposizioni(span_globali)
        if trace.attiva and len(span_obj) != len(pre):
            rimasti = set(map(id, span_obj))
            for r in pre:
                if id(r) not in rimasti:
                    trace.scartato(r, testo_analisi, "sovrapposizione",
                                   "perso contro uno span con priorità maggiore")

        # Merger post-analisi: due span PERSONA adiacenti separati solo
        # da una particella nobiliare ("de", "di", "della", "lo", ...)
        # vengono fusi in un unico span. Copre i casi "Serena Di
        # Giovanni" che il neurale emette come due PERSON separate.
        span_obj = _fondi_persone_con_particelle(span_obj, testo)

        # Propagazione cognomi confermati (fix 1b): "Rossi" isolato
        # dopo un "Mario Rossi" confermato diventa PERSONA (segnaposto
        # distinto, correlato in tabella).
        if "PERSONA" in cat_attive:
            span_obj = _propaga_cognomi_confermati(span_obj, testo_analisi)
            # Fix C: nomi in enumerazione confermati dai vicini certi.
            span_obj = _propaga_nomi_in_enumerazione(span_obj, testo_analisi)
            span_obj = _propaga_nomi_ripetuti(span_obj, testo_analisi)

        # 2. Preparazione mappa entità (per l'output) e sostituzione R→L.
        placeholder_per_valore: dict[str, dict] = {}

        # PRIMA PASSATA (ordine crescente di start): calcolo per ogni span
        # il placeholder da usare, applicando la RISOLUZIONE ENTITÀ
        # (GRUPPO A). La prima occorrenza di una chiave determina il
        # numero progressivo; occorrenze successive con la stessa chiave
        # riusano lo stesso placeholder anche se il valore letterale è
        # diverso ("Mario Rossi" e "Rossi" → «PERSONA_1»).
        assegnazioni: list[tuple[int, int, str, str, str]] = []
        # (start, end, valore_originale, placeholder, tipo)

        # Numeri già usati dal testo di partenza: vanno saltati, o al
        # ripristino le occorrenze preesistenti diventerebbero dati veri.
        riservati = identificatori_gia_nel_testo(testo)

        for sp in sorted(span_obj, key=lambda s: s.start):
            valore = testo[sp.start:sp.end]
            if not valore.strip():
                continue
            tipo = _tipo_di(sp.entity_type)
            chiave = chiave_di(valore, tipo)

            # Riuso del placeholder SOLO per forma letterale identica
            # (2026-07-31): il riuso per chiave normalizzata collassava
            # forme diverse ("Mario Rossi." con punto da OCR e
            # "Mario Rossi") sotto lo stesso placeholder, e al
            # ripristino usciva una sola delle due forme → G4 violata
            # su documenti reali. La chiave resta memorizzata come
            # informazione (correlazioni, ispezione).
            row = vault.get_by_valore(sessione_id, valore)

            if row is None:
                idx = _indice_libero(
                    tipo, vault.next_index(sessione_id, tipo), riservati
                )
                placeholder = f"{_PH_OPEN}{tipo}_{idx}{_PH_CLOSE}"
                vault.add(sessione_id, placeholder, valore, tipo, chiave_norm=chiave)
            else:
                placeholder = row["placeholder"]
                tipo = row["tipo"]

            assegnazioni.append((sp.start, sp.end, valore, placeholder, tipo))
            trace.accettato(valore, tipo, placeholder)

            # Aggiorna la mappa entità con la forma canonica (valore_reale
            # = quello di ``row`` se esisteva, altrimenti il letterale).
            valore_canonico = row["valore_reale"] if row is not None else valore
            entry = placeholder_per_valore.setdefault(
                placeholder,
                {
                    "placeholder": placeholder,
                    "valore_reale": valore_canonico,
                    "tipo": tipo,
                    "occorrenze": 0,
                },
            )
            entry["occorrenze"] += 1

        # SECONDA PASSATA (ordine decrescente): sostituisco nel testo
        # ogni span col placeholder corrispondente.
        out = testo
        for start, end, _val, placeholder, _tipo in sorted(
            assegnazioni, key=lambda t: t[0], reverse=True
        ):
            out = out[:start] + placeholder + out[end:]

        lista = list(placeholder_per_valore.values())
        # Ordinamento stabile per placeholder per un output prevedibile.
        lista.sort(key=lambda e: (e["tipo"], e["placeholder"]))

        # Compensazione informativa (non modifica il testo): per ogni
        # entità PERSONA/ORG segnalo il placeholder correlato più
        # probabile — es. «PERSONA_2» "Rossi" → correlato_a=«PERSONA_1»
        # "Mario Rossi". La UI mostra questa colonna in tabella. Se
        # l'ambiguità è multipla, il campo resta a None.
        for e in lista:
            altri = [x for x in lista if x is not e]
            e["correlato_a"] = correlato_a(e["valore_reale"], e["tipo"], altri)

        # Suggerimenti (livello 3): dedup per valore, non entrano nel
        # vault e non modificano il testo. La UI li mostrerà in una
        # sezione "Possibili entità" con la casella non spuntata.
        suggeriti_visti: set = set()
        for sp in span_suggeriti:
            valore = testo[sp.start:sp.end]
            if not valore.strip() or valore in suggeriti_visti:
                continue
            # Non emettere suggerimenti per valori che sono già stati
            # sostituiti come entità attive (evita rumore).
            if valore in placeholder_per_valore:
                continue
            # Fix E: né per testo già coperto da un'entità sostituita.
            # "via perugia 18" è già «INDIRIZZO_1»: proporre "perugia"
            # come persona è un doppione su testo che non esiste più.
            if any(sp.start < fine and inizio < sp.end
                   for inizio, fine, _v, _p, _t in assegnazioni):
                continue
            # Né per testo che nell'originale era tutto minuscolo. Il
            # candidato nasce dal pattern "iniziale maiuscola": su un
            # documento prevalentemente minuscolo quella maiuscola l'ha
            # messa il truecasing poche righe fa, non chi ha scritto. Se
            # l'unica prova che "che" sia un cognome è che noi stessi
            # l'abbiamo scritto "Che", la prova è circolare — e la lista
            # cognomi contiene abbastanza parole comuni ("che", "ali",
            # "costa", "the", "you") da riempire il riquadro dei
            # suggerimenti, che ne mostra cinque per volta, di sole
            # parole funzionali. I nomi minuscoli veri non passano di
            # qui: hanno un passaggio dedicato e finiscono al livello 1
            # o 2, sostituiti sul serio. Vale solo per i nomi: una
            # sequenza di cifre non ha maiuscole e il ragionamento sul
            # truecasing non la riguarda.
            if sp.entity_type == "IT_NOME_SUGGERITO" and not any(
                c.isupper() for c in valore
            ):
                continue
            suggeriti_visti.add(valore)
            lista.append(
                {
                    "placeholder": "",
                    "valore_reale": valore,
                    "tipo": _TIPO_SUGGERIMENTO.get(sp.entity_type, "PERSONA"),
                    "occorrenze": testo.count(valore),
                    "suggerito": True,
                }
            )

        if trace.attiva:
            registra(trace.eventi)

        return out, lista

    except Exception:
        # Rollback: scarta eventuali entità parziali non ancora persistite.
        if own_vault:
            vault.rollback()
        raise
    finally:
        avanzamento.termina()
        if own_vault:
            vault.close()


_TIPO_PULITO = re.compile(r"[^A-Z_]")


def _normalizza_tipo(tipo: str) -> str:
    pulito = _TIPO_PULITO.sub("", (tipo or "").strip().upper().replace(" ", "_"))
    pulito = pulito.strip("_")
    return pulito or "ALTRO"


def rianonimizza(
    testo: str,
    sessione_id: str,
    entita: list[dict],
    *,
    db_path: str | None = None,
) -> tuple[str, list[dict]]:
    """Riapplica al testo originale la mappatura entità decisa dall'utente.

    La lista ``entita`` è la sola fonte di verità: la sessione nel vault viene
    riscritta da zero, così i placeholder restano numerati in modo coerente
    dopo che l'utente ha tolto, aggiunto o ritipizzato delle righe.

    Se una voce porta con sé il ``placeholder`` che aveva già, e il tipo non
    è cambiato, quel segnaposto viene **riusato**. Serve alla modifica
    diretta sul testo: ogni ripristino o cambio tipo richiama questa
    funzione, e senza il riuso togliere una riga rinumererebbe tutte quelle
    dello stesso tipo — l'utente vedrebbe mezzo documento cambiare sotto
    gli occhi per un click solo. Chi cambia il tipo invece un numero nuovo
    lo vuole: è il senso dell'operazione.
    """

    if testo is None:
        return "", []

    vault = Vault(db_path or DEFAULT_DB_PATH)
    try:
        vault.clear_session(sessione_id)

        visti = set()
        puliti: list[tuple[str, str, str]] = []
        for e in entita or []:
            valore = (e.get("valore_reale") or "").strip()
            if not valore or valore in visti:
                continue
            visti.add(valore)
            puliti.append((
                valore,
                _normalizza_tipo(e.get("tipo", "")),
                (e.get("placeholder") or "").strip(),
            ))

        # I valori più lunghi vanno sostituiti per primi: altrimenti un valore
        # contenuto in un altro ("Rossi" dentro "Mario Rossi") lo spezzerebbe.
        puliti.sort(key=lambda t: len(t[0]), reverse=True)

        contatori: dict[str, int] = {}
        riservati = identificatori_gia_nel_testo(testo)

        # Prenoto i segnaposto da riusare prima di assegnarne di nuovi, così
        # un numero riusato non viene dato a un'altra riga.
        confermati: dict[str, str] = {}
        for valore, tipo, ph in puliti:
            m = _PH_REGEX.fullmatch(ph)
            if m is None:
                continue
            corpo_tipo, _, numero = m.group(1).rpartition("_")
            if corpo_tipo != tipo or (tipo, int(numero)) in riservati:
                continue
            riservati.add((tipo, int(numero)))
            confermati[valore] = ph

        out = testo
        risultato: list[dict] = []
        for valore, tipo, _ph in puliti:
            placeholder = confermati.get(valore)
            if placeholder is None:
                contatori[tipo] = _indice_libero(
                    tipo, contatori.get(tipo, 0) + 1, riservati
                )
                placeholder = f"{_PH_OPEN}{tipo}_{contatori[tipo]}{_PH_CLOSE}"
            occorrenze = out.count(valore)
            if occorrenze:
                out = out.replace(valore, placeholder)
            vault.add(sessione_id, placeholder, valore, tipo)
            risultato.append(
                {
                    "placeholder": placeholder,
                    "valore_reale": valore,
                    "tipo": tipo,
                    "occorrenze": occorrenze,
                }
            )

        risultato.sort(key=lambda e: _ordine_ph(e["placeholder"]))
        return out, risultato
    finally:
        vault.close()


# ---------------------------------------------------------------------------
# Regex tollerante per la deanonimizzazione
# ---------------------------------------------------------------------------
#
# Motivazione: quando l'utente incolla nel pannello Ripristina la risposta
# di un LLM, la formattazione originale «TIPO_N» quasi sempre non
# sopravvive. Il modello (o l'interfaccia di chat) riformatta i caporali
# in virgolette dritte/curve, oppure marca il segnaposto come codice
# (backtick, block markdown), oppure lo cita fra parentesi. Se la
# de-anonimizzazione richiede la forma canonica esatta, il pannello
# Ripristina è inutile — ed è quello che è successo.
#
# Regola: cerchiamo un TOKEN ``TIPO_N`` (dove TIPO è A-Z_, N è \d+)
# eventualmente racchiuso da una coppia di decorazioni note. La coppia
# viene consumata insieme al token, così non restano virgolette o
# asterischi orfani. Se non c'è decorazione, matcha il token nudo.
#
# Le decorazioni sono elencate esplicitamente in coppie bilanciate: mai
# consumiamo una decorazione "solitaria" (es. una sola virgoletta dritta
# adiacente) perché in generale non sappiamo se appartiene al segnaposto
# o al testo circostante.

_BODY = r"[A-Za-z][A-Za-z_]{0,30}\s*_\s*\d+"

_DECOR_PAIRS: list[tuple[str, str]] = [
    ("«", "»"),
    ("“", "”"),   # curly double quotes  " "
    ("‘", "’"),   # curly single quotes  ' '
    (r"\*\*", r"\*\*"),     # markdown bold
    ("__", "__"),           # markdown bold (underscore)
    (r"\*", r"\*"),         # markdown italic
    ("`", "`"),             # inline code
    (r'"', r'"'),           # straight double quote
    (r"'", r"'"),           # straight apostrophe
    (r"\[", r"\]"),
    (r"\(", r"\)"),
    ("<", ">"),
]

# Alternative in ordine di lunghezza decrescente (le forme "wrapped"
# prima della "naked": così re preferisce consumare anche la decorazione
# quando presente).
_alt = [rf"{o}\s*(?:{_BODY})\s*{c}" for o, c in _DECOR_PAIRS]
_alt.append(_BODY)  # naked fallback

_ANY_PH_RE = re.compile("|".join(_alt))
_BODY_ONLY_RE = re.compile(r"([A-Za-z][A-Za-z_]{0,30})\s*_\s*(\d+)")


def identificatori_gia_nel_testo(testo: str) -> set[tuple[str, int]]:
    """Coppie ``(TIPO, numero)`` che il testo di partenza già contiene.

    Il ripristino riconosce il segnaposto anche decorato o nudo — «CF_1»,
    [CF_1], "CF_1", **CF_1**, CF_1 — perché i modelli linguistici lo
    riformattano e l'utente non deve accorgersene. Il rovescio è che un
    testo che contiene già "CF_1" per conto suo verrebbe espanso al
    ripristino con un dato reale che lì non c'era mai stato: il testo
    torna diverso dall'originale e ci finisce dentro un codice fiscale
    vero. Non è teorico — succede in ogni documento che parla di
    anonimizzazione, ed è stato trovato su un PDF reale dell'utente.

    Sanare al ripristino non si può: lì l'originale non c'è più. Quindi
    l'assegnazione salta i numeri già occupati, l'occorrenza preesistente
    non corrisponde a nulla nel vault e resta intatta.
    """
    occupati: set[tuple[str, int]] = set()
    for m in _ANY_PH_RE.finditer(testo or ""):
        body = _BODY_ONLY_RE.search(m.group(0))
        if body is not None:
            occupati.add((body.group(1).upper(), int(body.group(2))))
    return occupati


def _indice_libero(tipo: str, proposto: int, riservati: set[tuple[str, int]]) -> int:
    """Primo numero ≥ ``proposto`` non ancora riservato per ``tipo``."""
    idx = proposto
    while (tipo, idx) in riservati:
        idx += 1
    riservati.add((tipo, idx))
    return idx


def _ordine_ph(placeholder: str) -> tuple[str, int]:
    """Chiave d'ordinamento di un segnaposto: il tipo, poi il numero come
    intero. Con i numeri riusati la numerazione diventa sparsa e l'ordine
    alfabetico metterebbe «PERSONA_10» prima di «PERSONA_9».
    """
    m = _PH_REGEX.fullmatch(placeholder or "")
    if m is None:
        return (placeholder or "", 0)
    tipo, _, numero = m.group(1).rpartition("_")
    return (tipo, int(numero))


def deanonimizza(
    testo: str,
    sessione_id: str,
    *,
    vault: Vault | None = None,
    db_path: str | None = None,
) -> tuple[str, dict]:
    """De-anonimizza ``testo`` sostituendo i placeholder noti coi valori reali.

    Ritorna ``(testo_ripristinato, report)`` con:
      - ``ripristinati``: lista di placeholder trovati e sostituiti
      - ``non_trovati``: placeholder presenti nel vault ma non nel testo
      - ``warning``: placeholder presenti nel testo ma sconosciuti al vault
    """

    if testo is None:
        return "", {"ripristinati": [], "non_trovati": [], "warning": []}
    if not isinstance(testo, str):
        raise TypeError("testo deve essere una stringa")

    own_vault = False
    if vault is None:
        vault = Vault(db_path or DEFAULT_DB_PATH)
        own_vault = True

    try:
        entita_vault = list(vault.all_for_session(sessione_id))
        placeholder_vault = {r["placeholder"] for r in entita_vault}

        ripristinati: list[str] = []
        warning: list[str] = []

        def _restore(match: re.Match) -> str:
            # Estraggo il body ``TIPO_N`` dall'intero match (che può
            # contenere anche la decorazione).
            body_m = _BODY_ONLY_RE.search(match.group(0))
            if body_m is None:
                return match.group(0)
            tipo = body_m.group(1).upper()
            num = body_m.group(2)
            candidate = f"{_PH_OPEN}{tipo}_{num}{_PH_CLOSE}"
            row = vault.get_by_placeholder(sessione_id, candidate)
            if row is None:
                if candidate not in warning:
                    warning.append(candidate)
                return match.group(0)
            ripristinati.append(candidate)
            # Sostituisco l'intero match, decorazione compresa: così se
            # arriva `"PERSONA_2"` non lascio virgolette orfane.
            return row["valore_reale"]

        out = _ANY_PH_RE.sub(_restore, testo)

        ripristinati_set = set(ripristinati)
        non_trovati = sorted(placeholder_vault - ripristinati_set)

        # Warning: elimino i duplicati preservando l'ordine di prima apparizione.
        warning_unici: list[str] = []
        visti = set()
        for w in warning:
            if w not in visti:
                warning_unici.append(w)
                visti.add(w)

        report = {
            "ripristinati": sorted(ripristinati_set),
            "non_trovati": non_trovati,
            "warning": warning_unici,
        }
        return out, report
    finally:
        if own_vault:
            vault.close()


# ---------------------------------------------------------------------------
# CLI di prova
# ---------------------------------------------------------------------------

def _cli() -> None:  # pragma: no cover - solo per uso manuale
    import argparse
    import json
    import sys
    import uuid

    parser = argparse.ArgumentParser(description="PrivacyBridge motore CLI")
    parser.add_argument("--sessione", default=str(uuid.uuid4()))
    parser.add_argument("--db", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("anonimizza")
    sub.add_parser("deanonimizza")
    args = parser.parse_args()

    testo = sys.stdin.read()
    if args.cmd == "anonimizza":
        out, ents = anonimizza(testo, args.sessione, db_path=args.db)
        json.dump(
            {"testo": out, "entita": ents, "sessione": args.sessione},
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
    else:
        out, report = deanonimizza(testo, args.sessione, db_path=args.db)
        json.dump(
            {"testo": out, "report": report, "sessione": args.sessione},
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )


if __name__ == "__main__":  # pragma: no cover
    _cli()
