# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Recognizer basato su dizionario per i nomi italiani colloquiali.

Il modello neurale (rizzo-pii-0.3B) è addestrato su testi formali:
non riconosce "Ciao sono Andrea" perché il nome di battesimo isolato
in una frase colloquiale non compare mai nel training. Per un
prodotto in mano a un professionista è un difetto grave — l'utente
scrive email, chat, presentazioni brevi ogni giorno.

Questo modulo implementa un recognizer complementare in tre livelli
di confidenza, guidato dai due dizionari
``data/liste/nomi_italiani.tsv`` e ``data/liste/cognomi_italiani.tsv``
(generati da ``scripts/build_liste_nomi.py``; vedi DECISIONI.md per
fonti e licenze).

Livelli (ordinati da alta a bassa confidenza):

  1. NON AMBIGUO — il termine è un nome/cognome che NON coincide con
     una parola comune italiana. "Andrea", "Giuseppe", "Ferrari" con
     iniziale maiuscola dentro una frase: sostituisci sempre.

  2. AMBIGUO IN CONTESTO FORTE — il termine è ambiguo ("Rosa",
     "Serena", "Angelo", "Marino") ma il contesto rende certa
     l'interpretazione:
       - dopo un verbo di presentazione: "sono X", "mi chiamo X",
         "qui è X";
       - dopo un titolo: "signor X", "sig.ra X", "dott. X", "ing. X",
         "avv. X", "geom. X", "il cliente X", "il fornitore X";
       - in formula di apertura: "Gentile X", "Caro X", "Egregio X";
       - in firma: dopo "Cordiali saluti", "Un saluto", oppure ultima
         riga del testo;
       - nome + cognome adiacenti (entrambi nelle liste).

  3. AMBIGUO SENZA CONTESTO — nessun contesto forte. Il recognizer
     lo emette come suggerimento (entity_type ``IT_NOME_SUGGERITO``)
     con score basso; il motore di anonimizzazione lo raccoglie in
     una sezione "possibili entità" della UI, dove l'utente decide.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from .percorsi import cartella_liste

logger = logging.getLogger("privacybridge.nomi_italiani")


# ---------------------------------------------------------------------------
# Caricamento dizionari
# ---------------------------------------------------------------------------

_LISTE_DIR = cartella_liste()


def _carica_vocabolario(path: Path) -> set[str]:
    """Set di parole comuni italiane (minuscole) — usato per rilevare
    ``inizio frase + nome comune`` che spesso è un uso avverbiale/
    aggettivale ("Serena giornata a tutti", "Fiore all'occhiello")."""
    if not path.exists():
        return set()
    vocab: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for riga in fh:
            w = riga.strip().lower()
            if w and w.isalpha():
                vocab.add(w)
    return vocab


def _carica_tsv(path: Path) -> tuple[set[str], set[str]]:
    """Ritorna (tutti_lower, ambigui_lower). Chiavi in minuscolo per
    match case-insensitive."""
    tutti: set[str] = set()
    ambigui: set[str] = set()
    if not path.exists():
        return tutti, ambigui
    with path.open(encoding="utf-8") as fh:
        for riga in fh:
            riga = riga.rstrip("\n")
            if not riga or riga.startswith("#"):
                continue
            parts = riga.split("\t")
            if len(parts) != 2:
                continue
            nome = parts[0].strip().lower()
            flag = parts[1].strip()
            if not nome:
                continue
            tutti.add(nome)
            if flag == "1":
                ambigui.add(nome)
    return tutti, ambigui


_NOMI_TUTTI, _NOMI_AMBIGUI = _carica_tsv(_LISTE_DIR / "nomi_italiani.tsv")
_COGN_TUTTI, _COGN_AMBIGUI = _carica_tsv(_LISTE_DIR / "cognomi_italiani.tsv")
_VOCAB_IT = _carica_vocabolario(_LISTE_DIR / "vocab_it_60k.txt")
# Vocabolario esteso (660k lemmi + forme flesse) — usato SOLO per la
# guardia "inizio frase + nome del seed + parola comune successiva".
# NON usato per la marcatura ambigui perché contiene anche molti nomi
# propri.
_VOCAB_IT_ESTESO = _carica_vocabolario(_LISTE_DIR / "vocab_it_660k.txt")

# Termini che pur essendo formalmente nel dizionario (es. "Gentile" è un
# cognome italiano vero) sono anche formule di saluto/apertura/chiusura
# molto più frequenti dell'omonimia. Se non li escludiamo, all'inizio di
# ogni email compare un finto suggerimento.
_FORMULE_ESCLUSE = {
    "gentile", "gentilissima", "gentilissimo",
    "caro", "cara", "carissimo", "carissima",
    "buongiorno", "buonasera", "buonanotte", "salve",
    "cordiali", "distinti", "cordialmente",
    "grazie", "prego", "ciao", "arrivederci",
    "egregio", "egregia", "spettabile",
    "signor", "signora", "signorina",
    "dottore", "dottoressa", "dottor",
    "professore", "professoressa", "avvocato", "avvocata",
    "ingegnere", "architetto", "geometra",
    "santo", "santa", "beato", "beata",  # frequentemente inizio frase
    # Titoli abbreviati (nel dizionario Wikidata compaiono anche come
    # "nomi", es. "Ing" — cognome tedesco raro — genera FP su "Ing.").
    "ing", "dott", "arch", "avv", "geom", "prof", "rag", "sig",
    "dr", "dr.ssa", "sig.ra", "sig.na",
    "fra", "don", "padre", "madre", "suora", "papa",
    # Termini di ruolo/relazione che il neurale tende a marcare come
    # nome e il dizionario ha come cognomi rari.
    "fratelli", "sorelle", "figlio", "figlia", "moglie", "marito",
    "presidente", "amministratore", "direttore", "responsabile",
    "condominio", "azienda", "societa", "impresa", "studio", "ufficio",
}

# Nomi e cognomi molto corti (1-2 caratteri) sarebbero mine anti-personali:
# "A" nella lista genererebbe centinaia di falsi positivi. Li rimuoviamo
# a monte del recognizer.
_NOMI_TUTTI    = {n for n in _NOMI_TUTTI    if len(n) >= 3}
_NOMI_AMBIGUI  = {n for n in _NOMI_AMBIGUI  if len(n) >= 3}
_COGN_TUTTI    = {n for n in _COGN_TUTTI    if len(n) >= 3}
_COGN_AMBIGUI  = {n for n in _COGN_AMBIGUI  if len(n) >= 3}


def _nome_noto(token_lc: str) -> bool:
    return token_lc in _NOMI_TUTTI


def _nome_ambiguo(token_lc: str) -> bool:
    return token_lc in _NOMI_AMBIGUI


def _cognome_noto(token_lc: str) -> bool:
    return token_lc in _COGN_TUTTI


def _cognome_ambiguo(token_lc: str) -> bool:
    return token_lc in _COGN_AMBIGUI


# Parole funzionali/comuni che NON possono essere cognomi anche se
# tecnicamente alfabetiche. Se il primo token è un nome noto ma il
# secondo è una parola funzionale, non estenderemo lo span.
_STOP_WORDS_COGNOME = {
    # articoli, preposizioni, congiunzioni
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
    "del", "della", "dello", "delle", "degli", "dei",
    "al", "alla", "allo", "alle", "agli", "ai",
    "dal", "dalla", "dallo", "dalle", "dagli", "dai",
    "sul", "sulla", "sullo", "sulle", "sugli", "sui",
    "e", "ed", "o", "od", "ma", "però", "quindi", "poi",
    "che", "chi", "cui", "come", "quando", "dove", "perché",
    # verbi ausiliari + presentazione tipici in questa posizione
    "è", "sono", "ho", "hai", "ha", "abbiamo", "avete", "hanno",
    "sei", "siete", "siamo",
    "era", "eravamo", "erano",
    "sta", "stanno", "stiamo",
    "va", "vado", "vai", "andiamo",
    "posso", "puoi", "può", "possiamo", "potete", "possono",
    "voglio", "vuoi", "vuole", "vogliamo", "volete", "vogliono",
    # avverbi frequenti
    "non", "solo", "anche", "ancora", "già", "sempre", "mai",
    "molto", "poco", "abbastanza", "quasi", "tanto",
    # frequenti nel testo post-nome
    "domani", "ieri", "oggi", "adesso", "ora",
    "qui", "qua", "là", "lì",
    # verbi di azione dopo il nome
    "arriva", "arriverà", "arrivo", "arrivi",
    "viene", "vengo", "vieni", "verrà",
    "chiama", "chiamo", "chiami",
    "dice", "dico", "dici", "dirà",
    "scrive", "scrivo", "scrivi",
    "lavora", "lavoro", "lavori",
    "manda", "mando", "mandi",
    "parla", "parlo", "parli",
    "fa", "faccio", "fai",
    "vede", "vedo", "vedi", "vedrà",
    "risponde", "rispondo", "rispondi",
    # data/nascita adiacenti
    "nato", "nata", "nati", "nate",
    "abita", "abito", "abiti",
    # nazionalità/luoghi che vengono spesso subito dopo un nome
    "italiano", "italiana", "italiani", "italiane",
}


# Particelle nobiliari / connettori nei cognomi italiani. In minuscolo
# ("de giovanni", "di marco", "lo bianco") non le vogliamo scartare
# come "troppo corte": sono parte del cognome.
_PARTICELLE_COGNOME_SHORT = {
    "de", "di", "da", "del", "dello", "della", "delle", "degli", "dei",
    "dal", "dalla", "dallo", "dalle", "dagli", "dai",
    "lo", "la", "le", "li",
    "van", "von", "der",
}


def _e_cognome_plausibile(tok_lc: str) -> bool:
    """True se ``tok_lc`` potrebbe plausibilmente essere un cognome,
    anche se NON presente nel dizionario cognomi (che è incompleto).

    Criteri: puramente alfabetico, >= 3 caratteri, NON stop-word e NON
    formula esclusa e NON parola comune nel vocabolario italiano.
    Le particelle di 2 caratteri (de, di, da, lo, la) sono ammesse.
    """
    if not tok_lc:
        return False
    # Particella nobiliare di 2 caratteri: OK.
    if tok_lc in _PARTICELLE_COGNOME_SHORT:
        return True
    if len(tok_lc) < 3:
        return False
    if not tok_lc.replace("'", "").isalpha():
        return False
    if tok_lc in _STOP_WORDS_COGNOME:
        return False
    if tok_lc in _FORMULE_ESCLUSE:
        return False
    # Se è già nel dizionario cognomi o nomi (case-insensitive), è
    # coperto altrove.
    if tok_lc in _NOMI_TUTTI or tok_lc in _COGN_TUTTI:
        return True
    # Parole molto comuni italiane (nel vocab) non sono cognomi
    # plausibili: se il vocab lo conosce come parola comune, meglio
    # scartare.
    return tok_lc not in _VOCAB_IT


# ---------------------------------------------------------------------------
# Detectori di contesto forte (livello 2)
# ---------------------------------------------------------------------------

# Verbi/formule di presentazione. Il nome segue immediatamente il verbo
# (eventualmente con un articolo).  Match a livello di riga per riscoprire
# la firma "Cordiali saluti,\nMario".
_VERBI_PRESENTAZIONE = re.compile(
    r"\b(?:"
    r"sono|mi\s+chiamo|qui\s+è|qui\s+e|"
    r"parla|vi\s+scrivo|ti\s+scrivo|sono\s+io|scrivo\s+io|"
    r"sono\s+stato\s+contattato\s+da|contattato\s+da|"
    r"presento|ti\s+presento|vi\s+presento|"
    r"da\s+parte\s+di|risposta\s+da|inoltrata\s+da"
    r")\b[\s,:]+",
    re.IGNORECASE,
)

_TITOLI = re.compile(
    r"\b(?:"
    r"il\s+signor|la\s+signora|la\s+signorina|"
    r"signor|signora|signorina|"
    r"sig\.?|sig\.?ra|sig\.?na|"
    r"dott\.?|dott\.?ssa|dott\.?sa|dottor|dottore|dottoressa|dr\.?|"
    r"ing\.?|ingegner|arch\.?|architetto|"
    r"avv\.?|avvocato|avvocata|"
    r"geom\.?|geometra|"
    r"prof\.?|professor|professore|professoressa|"
    r"rag\.?|ragionier|ragioniera|"
    r"il\s+cliente|la\s+cliente|"
    r"il\s+fornitore|la\s+fornitrice|"
    r"il\s+collega|la\s+collega|"
    r"il\s+paziente|la\s+paziente"
    r")\s+",
    re.IGNORECASE,
)

# Formule di apertura di email/lettere. Il nome (o cognome) segue.
_APERTURA = re.compile(
    r"(?:^|\n)(?:\s*[-•]\s*)?"
    r"(?:"
    r"gentile|gentilissima|gentilissimo|"
    r"caro|cara|carissimo|carissima|"
    r"egregio|egregia|"
    r"spett\.?le|spettabile|"
    r"buongiorno|buonasera|buon\s+pomeriggio|salve|ciao"
    r")[\s,]+",
    re.IGNORECASE,
)

# Formule di chiusura di email/lettere. Il nome (o cognome) segue.
_CHIUSURA = re.compile(
    r"(?:"
    r"cordiali\s+saluti|distinti\s+saluti|un\s+saluto|un\s+abbraccio|"
    r"a\s+presto|saluti|grazie\s+e\s+saluti|"
    r"cordialmente|con\s+i\s+migliori\s+saluti"
    r")[\s,.:!]*\n[\s\-—]*",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Analisi del testo
# ---------------------------------------------------------------------------

# Un candidato è una parola con iniziale maiuscola non preceduta da lettera
# (per evitare "Alessandro" in mezzo a "MarioAlessandro"). Escludiamo i
# caratteri di punteggiatura tipici e i confini alfa (word boundary).
_CANDIDATO_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])"                       # confine: nessuna lettera prima
    r"([A-ZÀÁÈÉÌÍÒÓÙÚ][a-zà-ÿ]{2,29})"        # inizio maiuscolo, min 3 char
    r"(?![A-Za-zÀ-ÿ])"                        # confine: nessuna lettera dopo
)

# Candidato "minuscolo" — case-insensitive per parole lunghe almeno 3
# caratteri, con confine alfabetico ai bordi. Usato SOLO subito dopo un
# contesto forte (verbo di presentazione, titolo, formula di apertura),
# perché scan indiscriminato dei minuscoli produrrebbe una valanga di
# falsi positivi (ogni parola comune con lookup nel dizionario diventerebbe
# candidata).
_CANDIDATO_LOWER_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])([a-zà-ÿ][a-zà-ÿ']{2,29})(?![A-Za-zÀ-ÿ])"
)

# Particelle nobiliari (2+ caratteri) intercettate esplicitamente: il
# pattern generale richiede ≥ 3 char e "de"/"di"/"da"/"lo"/"la" non
# passerebbero. Necessario per cognomi come "de giovanni", "di marco",
# "lo bianco".
_PARTICELLA_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])"
    r"(de|di|da|del|dello|della|delle|degli|dei|"
    r"dal|dalla|dallo|dalle|dagli|dai|lo|la|le|li|"
    r"d'|l'|dell'|dall'|nell'|sull'|all')"
    r"(?![A-Za-zÀ-ÿ])",
    re.IGNORECASE,
)


# Contesti forti che aprono la scansione minuscola. Ne distinguiamo due
# classi:
#
#  - INEQUIVOCABILE: la parola successiva è quasi sicuramente un nome
#    ("mi chiamo X", "signor X", "gentile X"). Con questi contesti
#    accettiamo anche nomi ambigui/nel-vocab come unico token.
#  - AMBIGUO: "sono X" può precedere sia nome ("sono Marco") sia
#    aggettivo ("sono felice"). Con solo primo token ambiguo scartiamo;
#    con nome+cognome plausibili accettiamo.
_CONTEXT_INEQUIVOCABILE = re.compile(
    r"\b(?:"
    r"mi\s+chiamo|"
    r"il\s+mio\s+nome\s+è|il\s+mio\s+nome\s+e|"
    r"nome:?|cognome:?|"
    r"il\s+signor|la\s+signora|la\s+signorina|"
    r"signor|signora|signorina|"
    r"sig\.?|sig\.?ra|sig\.?na|"
    r"dott\.?|dott\.?ssa|dott\.?sa|dottor|dottore|dottoressa|dr\.?|"
    r"ing\.?|ingegner|arch\.?|architetto|"
    r"avv\.?|avvocato|avvocata|"
    r"geom\.?|geometra|"
    r"prof\.?|professor|professore|professoressa|"
    r"il\s+cliente|la\s+cliente|il\s+fornitore|il\s+collega|il\s+paziente"
    r")\b[\s,:.]+"
    r"|(?:^|\n)(?:\s*[-•]\s*)?(?:"
    r"gentile|gentilissima|gentilissimo|"
    r"caro|cara|carissimo|carissima|"
    r"egregio|egregia|spett\.?le|spettabile"
    r")[\s,]+",
    re.IGNORECASE,
)

_CONTEXT_AMBIGUO = re.compile(
    r"\b(?:"
    r"sono|qui\s+è|qui\s+e|parla|vi\s+scrivo|ti\s+scrivo|"
    r"sono\s+io|scrivo\s+io|"
    r"sono\s+stato\s+contattato\s+da|contattato\s+da|"
    r"da\s+parte\s+di|risposta\s+da|inoltrata\s+da"
    r")\b[\s,:]+"
    r"|(?:^|\n)(?:\s*[-•]\s*)?(?:"
    r"buongiorno|buonasera|buon\s+pomeriggio|salve|ciao"
    r")[\s,]+",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Pass "nome certo in minuscolo" (chiusura classe caso "marco")
# ---------------------------------------------------------------------------
#
# Un nome del TSV NON ambiguo che coincide con una parola comune
# ("marco" = voce di marcare, "grazia", "rosa") in un testo minuscolo
# non viene mai ricapitalizzato dal truecasing (per non capitalizzare
# "io marco le presenze") e quindi non diventa mai candidato. La regola
# del briefing — la lista nomi ha priorità sul filtro vocabolario — si
# applica QUI con un contesto sintattico personale, perché la priorità
# cieca è insostenibile: fra i nomi non-ambigui in vocab ci sono
# "guido", "salvo", "massimo", "domenica" ("io guido", "salvo
# imprevisti", "il massimo", "domenica prossima").
#
# Trigger (uno basta):
#   - verbo di moto/permanenza + "da": "passo da", "ci vediamo da",
#     "sono passato da", "sto da";
#   - verbo con soggetto/oggetto personale immediatamente prima:
#     "viene X", "arriva X", "chiama X", "avvisa X", "saluta X", ...
#
# Nomi esclusi dal pass (uso temporale/idiomatico dominante anche in
# contesto verbale): domenica, natale, alba, sole, luce, salvo,
# massimo, santo, sante, fede, amore. Se servono, c'è la rubrica.

_TRIGGER_NOME_MINUSCOLO = re.compile(
    r"\b(?:"
    # moto/permanenza + "da"
    r"(?:vado|vai|va|andiamo|andate|vanno|"
    r"passo|passi|passa|passiamo|passato|passata|passati|"
    r"vediamo|vediamoci|rivediamo|"
    r"sto|stai|sta|stiamo|state|stanno|resto|resti|resta|restiamo|"
    r"ceno|ceni|cena|ceniamo|pranzo|pranzi|pranza|pranziamo|"
    r"dormo|dormi|dorme|dormiamo|torno|torni|torna|torniamo)"
    r"\s+da"
    # verbi con soggetto/oggetto personale
    r"|viene|vengono|verrà|verranno|veniva|venivano|"
    r"arriva|arrivano|arriverà|arriveranno|arrivava|"
    r"chiama|chiamo|chiami|chiamate|chiamerò|richiama|richiamo|"
    r"avvisa|avviso|avvisate|avvisiamo|"
    r"saluta|salutami|salutate|salutatemi|"
    r"invita|invito|invitiamo|invitate|"
    r"aspetta|aspetto|aspettiamo|aspettate|"
    r"incontro|incontri|incontriamo|incontrate|"
    r"sento|senti|sentiamo|sentite|"
    r"conosco|conosci|conosciamo|conoscete|"
    r"porto|porti|portiamo|portate|"
    r"c'è|c'era|"
    r"chiedo|chiedi|chiedete|chiediamo"
    r")\s+",
    re.IGNORECASE,
)

_NOMI_ESCLUSI_PASS_MINUSCOLO = {
    "domenica", "natale", "alba", "sole", "luce", "salvo",
    "massimo", "santo", "sante", "fede", "amore",
}


def _e_inizio_frase(testo: str, start: int) -> bool:
    """True se ``start`` è a inizio testo o dopo un terminatore
    (``.``/``!``/``?``/``\\n``) + whitespace."""
    if start == 0:
        return True
    # Guardo indietro saltando gli spazi.
    j = start - 1
    while j >= 0 and testo[j] in " \t\r":
        j -= 1
    if j < 0:
        return True
    return testo[j] in ".!?\n"


class NomeItalianoRecognizer(EntityRecognizer):
    """Riconosce nomi/cognomi italiani con i 3 livelli descritti nel docstring
    modulo. Emette:
     - ``IT_NOME_COGNOME`` (livello 1 e 2) con score 0.8;
     - ``IT_NOME_SUGGERITO`` (livello 3) con score 0.35 — sotto la soglia
       standard di 0.4: il motore lo può raccogliere separatamente per la
       UI di suggerimenti senza sostituire il testo.
    """

    def __init__(self):
        super().__init__(
            supported_entities=["IT_NOME_COGNOME", "IT_NOME_SUGGERITO"],
            supported_language="it",
            name="NomeItalianoRecognizer",
        )

    def load(self) -> None:  # pragma: no cover
        return None

    # ------------------------------------------------------------------ util

    def _contesto_forte(self, testo: str, start: int) -> bool:
        """True se il candidato che inizia in ``start`` è preceduto da
        una formula/titolo/verbo di presentazione, oppure appare in una
        firma di chiusura.
        """
        # Finestra di 40 caratteri prima del match: sufficiente per
        # frasi tipo "Il signor cliente Mario" o "mi chiamo Mario".
        finestra = testo[max(0, start - 40): start]

        # Presentazione + apertura + titolo alla FINE della finestra.
        for regex in (_VERBI_PRESENTAZIONE, _APERTURA, _TITOLI):
            m = list(regex.finditer(finestra))
            if m and m[-1].end() >= len(finestra) - 1:
                return True

        # Chiusura: cerchiamo prima della finestra estesa a 200 caratteri.
        finestra_larga = testo[max(0, start - 200): start]
        m = list(_CHIUSURA.finditer(finestra_larga))
        return bool(m and m[-1].end() >= len(finestra_larga) - 3)

    def _contesto_firma_finale(self, testo: str, start: int) -> bool:
        """Il candidato appartiene alla firma finale del documento?

        Regola: siamo negli ultimi 60 caratteri del testo E qualche riga
        sopra c'è una formula di chiusura ("Cordiali saluti", ecc.).
        """
        if start < len(testo) - 60:
            return False
        finestra = testo[max(0, start - 200): start]
        return bool(_CHIUSURA.search(finestra))

    # ------------------------------------------------------------- analyze

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        if not text or not text.strip():
            return []
        if not _NOMI_TUTTI:  # dizionario non caricato → recognizer inerte
            return []

        results: list[RecognizerResult] = []
        candidati = list(_CANDIDATO_RE.finditer(text))

        # -----------------------------------------------------------
        # Pass minuscolo: subito dopo un contesto forte, cerca nomi/
        # cognomi in minuscolo nel dizionario (fino a 2 token successivi).
        # Es. "ciao sono matteo rossi" — "matteo" è nome noto, "rossi"
        # è cognome di lista.  Emesso con confidenza alta perché
        # il contesto forte lo giustifica.
        # -----------------------------------------------------------
        emessi_lower: set[tuple[int, int]] = set()
        # Passo prima i contesti inequivocabili, poi gli ambigui.
        for ctx_m, ineq in [
            (m, True) for m in _CONTEXT_INEQUIVOCABILE.finditer(text)
        ] + [
            (m, False) for m in _CONTEXT_AMBIGUO.finditer(text)
        ]:
            cursor = ctx_m.end()

            # Salta spazi.
            j = cursor
            while j < len(text) and text[j] in " \t":
                j += 1
            if j >= len(text):
                continue

            # 1° token — DEVE essere in dizionario nomi o cognomi
            # (case-insensitive). Altrimenti nessun candidato qui.
            m1 = _CANDIDATO_LOWER_RE.match(text, j) or _CANDIDATO_RE.match(text, j)
            if m1 is None:
                continue
            tok1_lc = m1.group(1).lower()
            if tok1_lc in _FORMULE_ESCLUSE:
                continue
            primo_e_nome = _nome_noto(tok1_lc)
            primo_e_cognome = _cognome_noto(tok1_lc)
            if not (primo_e_nome or primo_e_cognome):
                continue

            span_start = m1.start(1)
            span_end = m1.end(1)

            # Token successivi (fino a 3 in più): particella nobiliare
            # + cognome ("de giovanni", "della valle", "lo bianco"), o
            # nome+cognome ("andrea rossi").
            cur = m1.end()
            prev_era_particella = False
            for _ in range(3):
                # Salta spazi.
                jn = cur
                while jn < len(text) and text[jn] in " \t":
                    jn += 1
                if jn >= len(text):
                    break
                # Prova nell'ordine: particella (per matchare "de"/"di"),
                # poi candidato minuscolo (3+ char), poi maiuscolo.
                mn = (
                    _PARTICELLA_RE.match(text, jn)
                    or _CANDIDATO_LOWER_RE.match(text, jn)
                    or _CANDIDATO_RE.match(text, jn)
                )
                if mn is None:
                    break
                tokn = mn.group(1)
                tokn_lc = tokn.lower()
                if tokn_lc in _FORMULE_ESCLUSE:
                    break
                particella = tokn_lc in _PARTICELLE_COGNOME_SHORT or tokn_lc.endswith("'")
                if particella:
                    span_end = mn.end(1)
                    cur = mn.end()
                    prev_era_particella = True
                    continue
                # Non è particella: valuta come nome/cognome.
                in_dizionario = _nome_noto(tokn_lc) or _cognome_noto(tokn_lc)
                cognome_plausib = (
                    primo_e_nome and _e_cognome_plausibile(tokn_lc)
                )
                # Dopo una particella nobiliare, il token successivo è
                # cognome anche se coincide con una parola comune del
                # vocab ("Della Valle", "Lo Bianco"): "valle" è nel
                # vocab ma nel contesto "della valle" è cognome.
                if prev_era_particella and (
                    len(tokn_lc) >= 3
                    and tokn_lc.replace("'", "").isalpha()
                    and tokn_lc not in _STOP_WORDS_COGNOME
                ):
                    span_end = mn.end(1)
                    cur = mn.end()
                    prev_era_particella = False
                    continue
                if in_dizionario or cognome_plausib:
                    span_end = mn.end(1)
                    cur = mn.end()
                    prev_era_particella = False
                    continue
                break

            if (span_start, span_end) in emessi_lower:
                continue

            # Sotto contesto AMBIGUO, se il PRIMO token è nel vocabolario
            # italiano (parola comune), scarta completamente — copre sia
            # "sono felice" (solo primo) sia "sono felice del risultato"
            # (primo + particella + parola). Il rischio è perdere "sono
            # marco" (marco in vocab): accettato perché era già
            # scartato dalla regola solo_primo precedente.
            if not ineq and tok1_lc in _VOCAB_IT:
                continue

            emessi_lower.add((span_start, span_end))
            results.append(
                RecognizerResult(
                    entity_type="IT_NOME_COGNOME",
                    start=span_start,
                    end=span_end,
                    score=0.85,   # contesto forte, alta confidenza
                )
            )

        # -----------------------------------------------------------
        # Pass "nome certo in minuscolo": trigger sintattico personale
        # + nome del TSV non ambiguo. Copre "viene marco con me",
        # "ci vediamo da grazia" in testo tutto minuscolo, dove il
        # truecasing non interviene (nome = parola comune del vocab).
        # -----------------------------------------------------------
        for ctx_m in _TRIGGER_NOME_MINUSCOLO.finditer(text):
            j = ctx_m.end()
            m1 = _CANDIDATO_LOWER_RE.match(text, j) or _CANDIDATO_RE.match(text, j)
            if m1 is None:
                continue
            tok_lc = m1.group(1).lower()
            if tok_lc in _FORMULE_ESCLUSE:
                continue
            if tok_lc in _NOMI_ESCLUSI_PASS_MINUSCOLO:
                continue
            if not (_nome_noto(tok_lc) and not _nome_ambiguo(tok_lc)):
                continue
            span = (m1.start(1), m1.end(1))
            if span in emessi_lower:
                continue
            emessi_lower.add(span)
            results.append(
                RecognizerResult(
                    entity_type="IT_NOME_COGNOME",
                    start=span[0],
                    end=span[1],
                    score=0.75,
                )
            )

        # Cache degli span già emessi per evitare duplicati adiacenti
        # (es. "Mario Rossi" emesso una volta come nome+cognome).
        emessi: set[tuple[int, int]] = set()

        for idx, m in enumerate(candidati):
            start, end = m.start(1), m.end(1)
            if (start, end) in emessi:
                continue

            tok = m.group(1)
            tok_lc = tok.lower()

            # Filtro formule di apertura/chiusura (mai emesse come nomi).
            if tok_lc in _FORMULE_ESCLUSE:
                continue

            # -----------------------------------------------------------
            # A. Nome + cognome adiacenti (span combinato) — livello 2
            # -----------------------------------------------------------
            if idx + 1 < len(candidati):
                m2 = candidati[idx + 1]
                # Adiacenti = separati solo da whitespace (uno spazio
                # tipicamente). Ignora casi come "Mario, Luigi" (virgola).
                gap = text[m.end(1): m2.start(1)]
                if re.fullmatch(r" ", gap or ""):
                    tok2 = m2.group(1)
                    tok2_lc = tok2.lower()
                    combo_nome_cognome = (
                        _nome_noto(tok_lc) and _cognome_noto(tok2_lc)
                    )
                    combo_nome_nome = (
                        _nome_noto(tok_lc) and _nome_noto(tok2_lc)
                    )
                    if combo_nome_cognome or combo_nome_nome:
                        span_end = m2.end(1)
                        results.append(
                            RecognizerResult(
                                entity_type="IT_NOME_COGNOME",
                                start=start,
                                end=span_end,
                                score=0.85,
                            )
                        )
                        emessi.add((start, span_end))
                        emessi.add((m2.start(1), m2.end(1)))
                        continue

            # -----------------------------------------------------------
            # B. Nome isolato — livelli 1 / 2 / 3
            # -----------------------------------------------------------
            noto_nome = _nome_noto(tok_lc)
            noto_cognome = _cognome_noto(tok_lc)

            if not (noto_nome or noto_cognome):
                continue

            ambiguo = (
                (noto_nome and _nome_ambiguo(tok_lc))
                or (noto_cognome and not noto_nome and _cognome_ambiguo(tok_lc))
            )
            solo_cognome = noto_cognome and not noto_nome

            # Guardia inizio-frase: nome del seed top ISTAT che coincide
            # con parola comune italiana ("Vittoria", "Fiore", "Bruno",
            # "Aurora") a inizio frase + parola successiva nel vocabolario
            # italiano ("Vittoria schiacciante", "Fiore all'occhiello",
            # "Aurora boreale") → declassa a suggerimento. L'inizio-frase
            # forza la maiuscola su qualunque parola: senza contesto
            # personale seguente non c'è modo di distinguere il nome
            # dall'uso comune.
            e_inizio = _e_inizio_frase(text, start)
            if (
                not ambiguo
                and noto_nome
                and tok_lc in _VOCAB_IT
                and e_inizio
            ):
                # Guarda la parola successiva.
                j = end
                while j < len(text) and text[j] in " \t":
                    j += 1
                k = j
                while k < len(text) and (text[k].isalpha() or text[k] == "'"):
                    k += 1
                prox_raw = text[j:k].lower()
                # Preposizione articolata / elisione ("all'occhiello",
                # "dell'anno") → prefisso è preposizione → uso comune.
                prefisso = prox_raw.split("'", 1)[0]
                declassa = False
                if prefisso in {"all", "dell", "sull", "dall", "nell",
                                "un", "d", "l"}:
                    declassa = True
                else:
                    prox = prox_raw.rstrip("'")
                    if (
                        prox
                        and (prox in _VOCAB_IT or prox in _VOCAB_IT_ESTESO)
                        and prox not in _NOMI_TUTTI
                        and prox not in _COGN_TUTTI
                    ):
                        declassa = True
                if declassa:
                    results.append(
                        RecognizerResult(
                            entity_type="IT_NOME_SUGGERITO",
                            start=start,
                            end=end,
                            score=0.35,
                        )
                    )
                    emessi.add((start, end))
                    continue

            if not ambiguo and not solo_cognome:
                # LIVELLO 1: nome noto NON ambiguo → sostituisci sempre,
                # indipendentemente dal contesto, dalla presenza di
                # cognome, dalle maiuscole.
                #
                # Motivazione (2026-07-30): "Giacomo", "Giovanni",
                # "Giuseppe", "Andrea", "Matteo" non sono parole
                # italiane. Non esiste una frase in cui significhino
                # altro che una persona. La cautela con contesto forte
                # serve per i nomi ambigui (Rosa, Serena, Grazia,
                # Fiore, Chiara — parole comuni), gestiti nel ramo
                # else più sotto.
                #
                # Se la lista `nomi_italiani.tsv` marca un nome come
                # non-ambiguo ma sperimentiamo falsi positivi in
                # produzione, il fix è nel TSV (marcare quel nome
                # come ambiguo o rimuoverlo), non nel recognizer.
                results.append(
                    RecognizerResult(
                        entity_type="IT_NOME_COGNOME",
                        start=start,
                        end=end,
                        score=0.8,
                    )
                )
                emessi.add((start, end))
                continue

            # Ambiguo o solo-cognome: serve contesto forte.
            forte = (
                self._contesto_forte(text, start)
                or self._contesto_firma_finale(text, start)
            )
            if forte:
                # LIVELLO 2: ambiguo con contesto forte.
                results.append(
                    RecognizerResult(
                        entity_type="IT_NOME_COGNOME",
                        start=start,
                        end=end,
                        score=0.7,
                    )
                )
                emessi.add((start, end))
            else:
                # LIVELLO 3: suggerimento, score sotto la soglia standard.
                #
                # Ma non se il token è una parola corrente dell'italiano.
                # Ai livelli 1 e 2 il dizionario ha la precedenza sul
                # vocabolario, ed è giusto: lì c'è una prova in più (nome
                # non ambiguo, oppure contesto personale esplicito). Qui
                # quella prova non c'è, la sola presenza in lista non
                # distingue il cognome Scarpa dalla scarpa, e le liste
                # anagrafiche italiane contengono qualche migliaio di
                # parole comuni. Senza questo controllo il riquadro
                # "Possibili entità" si riempie di "Alla", "Ora",
                # "Durante", "Data", "Secondo": misurati sui documenti
                # reali, 84 suggerimenti su cinque file di cui 4 persone.
                # Un elenco così l'utente impara a saltarlo, ed è peggio
                # che non averlo — dà l'impressione di aver controllato.
                #
                # Il prezzo è perdere il suggerimento sui cognomi che sono
                # anche parole ("Scarpa", "Conte", "Costa") quando
                # compaiono isolati e senza contesto. Con un contesto
                # qualsiasi salgono al livello 2 e vengono sostituiti sul
                # serio, quindi la perdita riguarda solo il caso in cui
                # non avevamo comunque alcun indizio.
                if tok_lc in _VOCAB_IT_ESTESO:
                    continue
                results.append(
                    RecognizerResult(
                        entity_type="IT_NOME_SUGGERITO",
                        start=start,
                        end=end,
                        score=0.35,
                    )
                )
                emessi.add((start, end))

        return results


# ---------------------------------------------------------------------------
# Registrazione (chiamato da nlp_engine.build_analyzer)
# ---------------------------------------------------------------------------

def build_nome_italiano_recognizer() -> NomeItalianoRecognizer | None:
    """Costruisce il recognizer se i dizionari sono presenti.

    Toggle di benchmark: se ``PRIVACYBRIDGE_NO_NOMI_IT=1`` il recognizer
    è disabilitato (utile per misurare il contributo del dizionario in
    ``benchmark/misura_dizionario.py``).
    """
    if os.environ.get("PRIVACYBRIDGE_NO_NOMI_IT"):
        logger.info("Dizionario nomi italiani disabilitato via env")
        return None
    if not _NOMI_TUTTI and not _COGN_TUTTI:
        logger.warning(
            "Dizionari nomi/cognomi mancanti in %s — recognizer disabilitato",
            _LISTE_DIR,
        )
        return None
    return NomeItalianoRecognizer()
