# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Misura se normalizzare le confusioni dell'OCR prima del rilevamento conviene.

L'OCR scambia caratteri che si somigliano: ``0``/``O``, ``1``/``l``/``I``,
``5``/``S``, ``rn``/``m``.  L'ipotesi da verificare è che rimettere a posto
quelle confusioni prima di analizzare il testo recuperi le entità che oggi
sfuggono perché arrivano rotte.

La misura va fatta **in entrambe le direzioni**, perché la sostituzione non
è gratuita: ogni ``0`` diventato ``O`` guasta un numero per ogni codice
fiscale che ripara.  Lo script quindi non conta solo quello che si guadagna
ma anche quello che si rompe, sullo stesso testo.

Tre varianti sul testo estratto dal documento dell'utente:

  originale     il testo dell'OCR com'è
  globale       tutte le confusioni applicate ovunque — la proposta letterale
  mirata        le confusioni applicate solo dentro finestre che hanno già
                la forma di un dato (16 caratteri tipo CF, 11 cifre tipo
                P.IVA, sequenze di 13-19 cifre), lasciando intatto il resto

Per ciascuna: entità attive, entità perse rispetto all'originale, entità
nuove, e i valori delle une e delle altre.  Il verdetto si legge dalla
differenza, non dal totale.

Nota sugli offset: ``rn``→``m`` accorcia il testo di un carattere.  Una
normalizzazione che cambia lunghezza sposta tutte le posizioni successive
e rende impossibile il ripristino byte-esatto (garanzia G4).  Le varianti
qui misurate sono tutte a lunghezza costante tranne ``rn``→``m``, che è
misurata a parte proprio per quantificare che cosa costerebbe.

Uso:
    venv/bin/python -m benchmark.ocr_normalizza
    venv/bin/python -m benchmark.ocr_normalizza --file "Indagine .pdf"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from benchmark import CATEGORIE_CONSEGNA, isola, vault_isolato

isola("ocrnorm")

VAULT_DB = vault_isolato("ocrnorm")
ESTRATTI = ROOT / "benchmark" / "documenti_utente" / "estratti"

# Le confusioni tipiche, nella direzione che ripara una lettera scambiata
# per cifra.  La direzione opposta (lettera → cifra) serve ai numeri ed è
# incompatibile con questa: non si possono applicare tutte e due.
VERSO_LETTERA = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B"})
VERSO_CIFRA = str.maketrans({"O": "0", "l": "1", "I": "1", "S": "5", "B": "8"})

# Finestre che hanno già la forma di un dato, con i caratteri sbagliati
# ancora dentro: è qui che la correzione ha senso, e solo qui.
FORMA_CF = re.compile(r"\b[A-Z0-9]{6}[A-Z0-9]{2}[A-Z0-9][A-Z0-9]{2}[A-Z0-9][A-Z0-9]{3}[A-Z0-9]\b")
FORMA_NUM = re.compile(r"\b[0-9OlISB]{11,19}\b")


def _globale(testo: str) -> str:
    return testo.translate(VERSO_LETTERA)


def _mirata(testo: str) -> str:
    """Corregge dentro le finestre che hanno la forma di un dato.

    Un codice fiscale ha lettere e cifre in posizioni fisse: dentro quella
    finestra si sa quale verso applicare carattere per carattere.  Fuori
    non si sa, e infatti fuori non si tocca niente.
    """
    fuori = list(testo)

    def _cf(m: re.Match[str]) -> None:
        s = m.group(0)
        if len(s) != 16:
            return
        # CCCCCC NN C NN C NNN C  — sei lettere, due cifre, lettera, due
        # cifre, lettera, tre cifre, lettera.
        schema = "LLLLLLNNLNNLNNNL"
        for k, (car, tipo) in enumerate(zip(s, schema)):
            nuovo = car.translate(VERSO_LETTERA if tipo == "L" else VERSO_CIFRA)
            fuori[m.start() + k] = nuovo

    def _num(m: re.Match[str]) -> None:
        s = m.group(0)
        if sum(c.isdigit() for c in s) < len(s) - 3:
            return  # troppe lettere: è una parola, non un numero guasto
        for k, car in enumerate(s):
            fuori[m.start() + k] = car.translate(VERSO_CIFRA)

    for m in FORMA_CF.finditer(testo):
        _cf(m)
    for m in FORMA_NUM.finditer(testo):
        _num(m)
    return "".join(fuori)


def _rn_m(testo: str) -> str:
    return testo.replace("rn", "m")


def _attive(testo: str, sess: str, cat: set[str]) -> dict[tuple[str, str], int]:
    from backend.motore import anonimizza

    _, ents = anonimizza(testo, sess, db_path=VAULT_DB, categorie_attive=cat)
    fuori: dict[tuple[str, str], int] = {}
    for e in ents:
        if e.get("suggerito") or not e.get("placeholder"):
            continue
        fuori[(e["tipo"], e["valore_reale"])] = e.get("occorrenze", 1)
    return fuori


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default="Indagine .pdf.txt",
                    help="nome del dump in documenti_utente/estratti/")
    ap.add_argument("--categorie", choices=["consegna", "tutte"], default="consegna")
    args = ap.parse_args()

    sorgente = ESTRATTI / args.file
    if not sorgente.exists():
        disponibili = sorted(p.name for p in ESTRATTI.glob("*.txt"))
        print(f"non trovato: {sorgente}\ndisponibili: {disponibili}")
        return 1
    testo = sorgente.read_text(encoding="utf-8")

    from backend.motore import CATEGORIE_TUTTE, reset_analyzer
    reset_analyzer()
    cat = set(CATEGORIE_TUTTE) if args.categorie == "tutte" else set(CATEGORIE_CONSEGNA)

    print(f"testo: {args.file} — {len(testo):,} caratteri, categorie={args.categorie}\n")

    varianti = [
        ("originale", testo),
        ("globale", _globale(testo)),
        ("mirata", _mirata(testo)),
        ("rn→m", _rn_m(testo)),
    ]

    base: dict[tuple[str, str], int] = {}
    for nome, variante in varianti:
        ents = _attive(variante, f"norm-{nome}", cat)
        if nome == "originale":
            base = ents
            print(f"{nome:<12} {len(ents):>4} entità   (riferimento)"
                  f"   Δlunghezza {len(variante) - len(testo):+d}")
            continue
        nuove = {k: v for k, v in ents.items() if k not in base}
        perse = {k: v for k, v in base.items() if k not in ents}
        print(f"{nome:<12} {len(ents):>4} entità   +{len(nuove)} nuove  "
              f"−{len(perse)} perse   Δlunghezza {len(variante) - len(testo):+d}")
        for etichetta, ins in (("nuove", nuove), ("perse", perse)):
            if not ins:
                continue
            print(f"    {etichetta}:")
            for (tipo, val), occ in sorted(ins.items())[:20]:
                mostrato = val.replace("\n", "⏎")
                print(f"      {tipo:<14} {mostrato!r}  ×{occ}")
            if len(ins) > 20:
                print(f"      (+{len(ins) - 20} altre)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
