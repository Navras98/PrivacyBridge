# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Truecasing: ricapitalizza il testo minuscolo prima dell'analisi PII.

Motivazione strutturale: il motore neurale (rizzo-pii) è addestrato
su testo formale capitalizzato. Su testo minuscolo ("ciao sono matteo
rossi abito a taranto") NON riconosce niente, e da lì è nata tutta
la logica a contesti dedicata al minuscolo — che continuiamo a dover
estendere ogni volta con nuovi lemmi ("abito", "vivo", ...).

Approccio: se il testo è prevalentemente minuscolo, produce una
copia con capitalizzazione ricostruita (truecasing) preservando la
lunghezza, passa la copia all'analyzer, e riporta gli span sul testo
originale (offset coincidenti).

Dopo il truecasing, TUTTA la logica maiuscola-friendly funziona anche
sul minuscolo: il pass "contesti dedicati" diventa un rinforzo per
casi limite, non il meccanismo principale.

API pubblica:
    ricapitalizza(testo)        → (testo_ricapitalizzato, e_stato_modificato)
    prevalentemente_minuscolo(testo) → bool
"""

from __future__ import annotations

import re
from pathlib import Path

from .percorsi import cartella_liste

_LISTE_DIR = cartella_liste()


# ---------------------------------------------------------------------------
# Caricamento dizionari (nomi/cognomi/comuni)
# ---------------------------------------------------------------------------

def _leggi_tsv_prima_colonna(path: Path) -> set[str]:
    """Legge la prima colonna (case-insensitive → lower)."""
    if not path.exists():
        return set()
    out: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for riga in fh:
            riga = riga.rstrip("\n")
            if not riga or riga.startswith("#"):
                continue
            testo = riga.split("\t")[0].strip()
            if testo:
                out.add(testo.lower())
    return out


def _leggi_lista(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for riga in fh:
            riga = riga.strip()
            if not riga or riga.startswith("#"):
                continue
            out.add(riga.lower())
    return out


# Carichiamo il vocabolario PRIMA delle liste, così possiamo filtrare
# _COMUNI_TOKENS ed evitare che parole comuni ("con", "dei", "monte"
# — che compaiono come token in comuni multi-parola tipo "Beregazzo
# con Figliaro") vengano trattate come toponimi.
# Vocabolario italiano: 60k lemmi (conservativo). Non è ideale — mancano
# parole basilari come "gatto" — ma il 660k contiene anche nomi propri
# comuni ("luca", "mario") e blocca capitalizzazioni legittime. Il
# compromesso: la passata "particella" gestisce i cognomi ambigui, il
# recognizer nomi in minuscolo gestisce i nomi noti senza contesto.
_VOCAB_RAW: set[str] = _leggi_lista(_LISTE_DIR / "vocab_it_60k.txt")

_NOMI = _leggi_tsv_prima_colonna(_LISTE_DIR / "nomi_italiani.tsv")
_COGNOMI = _leggi_tsv_prima_colonna(_LISTE_DIR / "cognomi_italiani.tsv")
_COMUNI = _leggi_lista(_LISTE_DIR / "comuni_italiani.txt")

_VOCAB_IT: set[str] = _VOCAB_RAW

# Toponimi multi-parola: costruisco anche un indice dei singoli token
# ("reggio" da "reggio emilia") perché nel testo il match avviene
# token-per-token. Includiamo però solo i token >= 4 caratteri E NON
# nel vocabolario italiano (evita "con", "dei", "monte" — parole
# funzionali che compaiono in nomi di comuni multi-parola).
_COMUNI_TOKENS: set[str] = set()
for _c in _COMUNI:
    for _t in _c.replace("-", " ").split():
        if len(_t) >= 4 and _t not in _VOCAB_IT:
            _COMUNI_TOKENS.add(_t)


# Formule/titoli che NON vanno capitalizzate anche se coincidono con
# entrate nella lista nomi/cognomi ("Ing" era un nome esotico Wikidata,
# ma "ing." è l'abbreviazione di ingegnere).
_FORMULE_NON_CAPITALIZZARE = {
    "ing", "dott", "arch", "avv", "geom", "prof", "rag", "sig", "dr",
    "gentile", "buongiorno", "buonasera", "salve", "ciao", "arrivederci",
    "grazie", "prego", "cordiali", "distinti",
    "signor", "signora", "signorina",
    "papa", "san", "santo", "santa",
    "amministratore", "direttore", "presidente",
}


def _capitalizzabile_come_nome(token_lc: str) -> bool:
    """True se ``token_lc`` è un nome/cognome noto e NON è una parola
    comune italiana (evita di capitalizzare 'rosa' quando è fiore)."""
    if token_lc in _FORMULE_NON_CAPITALIZZARE:
        return False
    if token_lc not in _NOMI and token_lc not in _COGNOMI:
        return False
    return token_lc not in _VOCAB_IT


def _capitalizzabile_come_toponimo(token_lc: str) -> bool:
    """True se ``token_lc`` è un comune italiano noto e NON è parola
    comune (evita di capitalizzare 'roma' quando è nome di un romanzo,
    ma 'roma' è più spesso città → accettiamo)."""
    # I toponimi coincidono raramente con parole comuni: ammettiamo anche
    # quelli in vocabolario (Roma è città più spesso che parola).
    return token_lc in _COMUNI or token_lc in _COMUNI_TOKENS


# Particelle nobiliari / connettori: SEMPRE minuscole in truecasing
# (a metà cognome le lasciamo lower — "Mario De Rossi"). Lo lasciamo
# in lowercase; è il testo intorno che deciderà cosa fare.
_PARTICELLE_COGNOME = {
    "de", "di", "da", "del", "dello", "della", "delle", "degli", "dei",
    "dal", "dalla", "dallo", "dalle", "dagli", "dai",
    "lo", "la", "le", "li",
    "van", "von", "der", "d'", "l'",
}


# ---------------------------------------------------------------------------
# Rilevamento minuscolo dominante
# ---------------------------------------------------------------------------

_PAROLA_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']*")


def prevalentemente_minuscolo(testo: str, soglia: float = 0.3) -> bool:
    """True se meno di ``soglia`` (default 30%) delle parole ha
    iniziale maiuscola. In un testo formale in italiano tipicamente
    almeno il 5-15% delle parole (nomi propri, inizio frase) è
    capitalizzato; su testo chat/minuscolo la percentuale scende
    sotto il 5%."""
    parole = _PAROLA_RE.findall(testo)
    if len(parole) < 3:
        return False
    cap = sum(1 for p in parole if p[0].isupper())
    frazione_cap = cap / len(parole)
    return frazione_cap < soglia


# ---------------------------------------------------------------------------
# Ricapitalizzazione (preserva lunghezza per offset stabili)
# ---------------------------------------------------------------------------

_FINE_FRASE_RE = re.compile(r"[.!?]\s+|\n\s*|^")


def ricapitalizza(testo: str) -> tuple[str, bool]:
    """Ritorna ``(testo_ricap, modificato)``.

    Applica:
      1. Iniziale di frase (dopo `.`/`?`/`!`/`\\n` o inizio testo)
         → maiuscola.
      2. Ogni token il cui lemma minuscolo è nel dizionario nomi/
         cognomi/comuni (con filtro anti-parole-comuni) → prima lettera
         maiuscola.

    NB: la lunghezza del testo NON cambia: sostituiamo lettera per
    lettera senza aggiungere/togliere caratteri, così gli offset degli
    span emessi dall'analyzer coincidono col testo originale.
    """
    chars = list(testo)  # mutable per sostituzione in-place
    modificato = False

    def _upper_char_at(i: int) -> None:
        nonlocal modificato
        c = chars[i]
        if c.islower():
            chars[i] = c.upper()
            modificato = True

    # 1. Iniziale di frase.
    for m in _FINE_FRASE_RE.finditer(testo):
        pos = m.end()
        # Salta whitespace iniziali che sono nel gruppo di match
        # (già inclusi in m.end() perché il pattern li mangia).
        if pos < len(testo) and testo[pos].isalpha() and testo[pos].islower():
            _upper_char_at(pos)

    # 2. Token nel dizionario.
    for m in _PAROLA_RE.finditer(testo):
        tok = m.group(0)
        tok_lc = tok.lower()
        start = m.start()

        # Salta se il token è già capitalizzato.
        if tok[0].isupper():
            continue

        # Le particelle nobiliari nei cognomi NON vengono capitalizzate.
        if tok_lc in _PARTICELLE_COGNOME:
            continue

        # Capitalizza se noto come nome/cognome o toponimo.
        if _capitalizzabile_come_nome(tok_lc) or _capitalizzabile_come_toponimo(tok_lc):
            _upper_char_at(start)

    # 3. Passata "cognomi con particella nobiliare adiacente":
    # dopo un token già capitalizzato, se compare una particella
    # ("de", "di", "della", "lo", "la"...) seguita da una parola
    # minuscola, capitalizza sia la particella che la parola. Copre
    # "Luca lo bianco" → "Luca Lo Bianco", "Anna della valle" →
    # "Anna Della Valle".  Il rischio FP è limitato perché il pattern
    # richiede un nome/cognome capitalizzato PRIMA (dalla passata 2).
    tokens = list(_PAROLA_RE.finditer("".join(chars)))
    for i in range(len(tokens) - 2):
        cur_tok = tokens[i]
        part_tok = tokens[i + 1]
        cog_tok = tokens[i + 2]
        cur_val = "".join(chars[cur_tok.start(): cur_tok.end()])
        part_val = "".join(chars[part_tok.start(): part_tok.end()])
        cog_val = "".join(chars[cog_tok.start(): cog_tok.end()])
        if not cur_val or not cur_val[0].isupper():
            continue
        if part_val.lower() not in _PARTICELLE_COGNOME:
            continue
        # La parola dopo deve essere alfabetica ≥ 3 char e non stop-word
        # ovvia (verbi comuni). Uso il criterio: se già nel dizionario
        # cognomi la accettiamo sicuramente; altrimenti richiediamo che
        # non sia in un piccolo set di parole comuni che seguono
        # spesso una particella ma non sono cognomi.
        cog_lc = cog_val.lower()
        stop_dopo_part = {
            "posso", "puoi", "può", "possiamo", "potete", "possono",
            "voglio", "vuoi", "vuole", "vogliamo", "volete", "vogliono",
            "so", "sai", "sa", "sappiamo", "sapete", "sanno",
            "vedo", "vedi", "vede", "vediamo", "vedete", "vedono",
            "faccio", "fai", "fa", "facciamo", "fate", "fanno",
            "dico", "dici", "dice", "diciamo", "dite", "dicono",
            "penso", "pensi", "pensa", "pensiamo", "pensate", "pensano",
            "credo", "credi", "crede", "crediamo", "credete", "credono",
            "aspetto", "aspetti", "aspetta", "aspettano",
            "conosco", "conosci", "conosce", "conosciamo", "conoscete", "conoscono",
            "chiamo", "chiami", "chiama", "chiamiamo", "chiamate", "chiamano",
            "arrivo", "arrivi", "arriva", "arriviamo", "arrivate", "arrivano",
            "vado", "vai", "va", "andiamo", "andate", "vanno",
            "porto", "porti", "porta", "portiamo", "portate", "portano",
        }
        if cog_lc in stop_dopo_part:
            continue
        if len(cog_lc.replace("'", "")) < 3 or not cog_lc.replace("'", "").isalpha():
            continue
        # La parola dopo la particella deve essere un cognome noto (o
        # nome). Senza questo check "felice del risultato" verrebbe
        # capitalizzato in "Felice Del Risultato" perché "risultato"
        # è alfabetico >=3 char.
        if cog_lc not in _COGNOMI and cog_lc not in _NOMI:
            continue
        # Capitalizza particella e parola dopo.
        _upper_char_at(part_tok.start())
        _upper_char_at(cog_tok.start())

    return "".join(chars), modificato
