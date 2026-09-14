# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Corpus di 30 frasi colloquiali/informali per la FASE 2.

Contenuti tipici: chat brevi, messaggi email informali, presentazioni
in prima persona, firme rapide. Ogni frase ha almeno UN nome proprio
italiano; il campo ``entita`` elenca i valori attesi come PII (nomi
di persona e cognomi che devono essere trattenuti).

Scopo: misurare fuga (recall) e falsi positivi (precision) prima e
dopo l'introduzione del dizionario nomi italiani.
"""

from __future__ import annotations

# (frase, [entità attese])
FRASI: list[tuple[str, list[str]]] = [
    # ------------------------------------------------------- presentazione
    ("Ciao sono Andrea, ti scrivo per il preventivo.", ["Andrea"]),
    ("Buongiorno, mi chiamo Elisa e vorrei prenotare per due.", ["Elisa"]),
    ("Salve, qui è Simone del reparto acquisti.", ["Simone"]),
    ("Ehilà, sono Federica, la nuova del team!", ["Federica"]),
    ("Sto scrivendo per conto di Luca, il capocantiere.", ["Luca"]),

    # ------------------------------------------------------ chat/messaggi
    ("Ci vediamo domani da Marco alle otto.", ["Marco"]),
    ("Ho parlato con Rosa in mensa, dice che va bene.", ["Rosa"]),
    ("Passa a prendermi tu o mando Giacomo?", ["Giacomo"]),
    ("Chiedo a Giulia se ha finito il report.", ["Giulia"]),
    ("Ok, avviso io Paolo e Anna della modifica.", ["Paolo", "Anna"]),

    # -------------------------------------------------- email informali
    ("Ciao Marta,\nti giro il file come promesso.\nA presto,\nEnrico",
     ["Marta", "Enrico"]),
    ("Buonasera Federico, allego il preventivo aggiornato. Fammi sapere.",
     ["Federico"]),
    ("Grazie mille Chiara, ci sentiamo la prossima settimana.",
     ["Chiara"]),
    ("Riferisco a Roberto e ti aggiorno appena posso.", ["Roberto"]),
    ("Ciao Lorenzo, va bene giovedì?", ["Lorenzo"]),

    # ------------------------------- nomi ambigui in contesto forte
    ("Ho chiamato Serena stamattina, la richiama poi lei.", ["Serena"]),
    ("La consegna la fa Angelo, il collega di turno.", ["Angelo"]),
    ("Passala al signor Marino, se la trova.", ["Marino"]),
    ("La firma è di Grazia, non di sua sorella.", ["Grazia"]),
    ("Ha risposto Bianca, tutto ok.", ["Bianca"]),

    # ------------------------------------- presentazioni brevi / firme
    ("Un saluto,\nGiuseppe", ["Giuseppe"]),
    ("Grazie,\nMartina", ["Martina"]),
    ("Cordiali saluti,\nGabriele Ferrari", ["Gabriele Ferrari"]),
    ("A presto,\nSara", ["Sara"]),
    ("Ci sentiamo!\nDavide", ["Davide"]),

    # --------------------------- nome + cognome informali
    ("Dice Fabio Costa che possiamo iniziare lunedì.", ["Fabio Costa"]),
    ("La lezione la tiene Silvia Bianchi.", ["Silvia Bianchi"]),
    ("Ci penso io, poi passo la mano a Nicolò Neri.", ["Nicolò Neri"]),

    # ------------------------------------ colloquiale con più entità
    ("Ho visto Alessandro e Valentina al bar prima.",
     ["Alessandro", "Valentina"]),
    ("Domani ci sono Michele, Alberto e Camilla in riunione.",
     ["Michele", "Alberto", "Camilla"]),
]


# ---------------------------------------------------------------------------
# Frasi minuscolo (chat, messaggi rapidi): nomi/cognomi tutti in minuscolo.
# La FASE 2.follow-up ha aggiunto il pass "post-contesto" che li cattura.
# ---------------------------------------------------------------------------

FRASI_MINUSCOLO: list[tuple[str, list[str]]] = [
    ("ciao sono matteo rossi",                        ["matteo rossi"]),
    ("mi chiamo andrea rossi",                         ["andrea rossi"]),
    ("salve sono luca bianchi",                        ["luca bianchi"]),
    ("ciao a tutti, sono elena, la nuova",             ["elena"]),
    ("mi chiamo giuseppe, piacere",                    ["giuseppe"]),
    ("qui parla marco, richiamami tu",                 ["marco"]),
    ("ciao mario, come stai?",                         ["mario"]),
    ("gentile paolo, ti allego il file",               ["paolo"]),
    ("egregio signor bianchi, la disturbo per...",     ["bianchi"]),
    ("dott. rossi, la ringrazio della disponibilità",  ["rossi"]),
    ("scrivo io, giulio, per conto del reparto",       ["giulio"]),
    ("il signor lombardi ha chiamato ieri",            ["lombardi"]),
    ("ing. ferrari mi ha girato la mail",              ["ferrari"]),
    ("avv. moretti la richiamerà oggi",                ["moretti"]),
    ("ciao carlo, ci vediamo dopo",                    ["carlo"]),
]


# Trap in minuscolo: casi in cui NON deve essere emessa nessuna persona.
FRASI_MINUSCOLO_TRAP: list[str] = [
    "sono felice del risultato di oggi",
    "sono contento che sia finita",
    "sono andato al mare stamattina",
    "il colore rosa è di moda",
    "grazie ancora per il regalo",
]

assert len(FRASI_MINUSCOLO) == 15, f"attese 15 frasi minuscolo, trovate {len(FRASI_MINUSCOLO)}"


assert len(FRASI) == 30, f"attese 30 frasi, trovate {len(FRASI)}"


# ---------------------------------------------------------------------------
# Frasi trap: NON contengono PII di persona (ma contengono parole
# ambigue che potrebbero essere scambiate: rosa, grazia, bianco, ecc.).
# Servono per misurare i falsi positivi.
# ---------------------------------------------------------------------------

FRASI_TRAP: list[str] = [
    "Il maglione è di colore rosa acceso, ma non troppo.",
    "Bianco pulito, come vuole la nonna.",
    "Grazie a tutti per il regalo!",
    "Le olive del monte sono ottime quest'anno.",
    "Il fiore preferito della primavera è il tulipano.",
    "La pace è un valore che non ha prezzo.",
    "Serena giornata a tutti e buon lavoro.",
    "Angelo custode: figura tradizionale del cristianesimo.",
    "Il mio motto è: gioia semplice ogni giorno.",
    "Costa poco e rende molto, come promesso.",
    "Marino: aggettivo relativo al mare.",
    "Bruno è il colore preferito di molti.",
    "Vittoria schiacciante per la squadra ospite.",
    "La celeste volta stellata sopra di noi.",
    "Fiore all'occhiello del catalogo primaverile.",
]
