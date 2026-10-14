# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Verifica una per una le entità estratte da un PDF scansionato.

Il rilevamento su documento scansionato non era mai stato controllato: il
motore dichiara N entità e nessuno aveva guardato se sono dati veri o
rumore prodotto dagli errori di lettura dell'OCR. Questo script estrae il
testo con la stessa pipeline dell'applicazione (OCR di sistema incluso),
lancia il motore e stampa **ogni entità con il suo contesto**, così che il
giudizio si dia leggendo il documento invece di fidarsi del motore.

Salva anche il testo estratto su file: senza, non si può controllare a
mano un'occorrenza dubbia.

Uso:
    python benchmark/verifica_ocr.py "benchmark/documenti_utente/Indagine .pdf"
    python benchmark/verifica_ocr.py <pdf> --contesto 90
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CONTESTO_DEFAULT = 70
MAX_OCCORRENZE_MOSTRATE = 3


def _contesto(testo: str, inizio: int, fine: int, raggio: int) -> str:
    a = max(0, inizio - raggio)
    b = min(len(testo), fine + raggio)
    prima = testo[a:inizio].replace("\n", "⏎")
    dentro = testo[inizio:fine].replace("\n", "⏎")
    dopo = testo[fine:b].replace("\n", "⏎")
    return f"…{prima}⟦{dentro}⟧{dopo}…"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", help="percorso del PDF da verificare")
    ap.add_argument("--contesto", type=int, default=CONTESTO_DEFAULT,
                    help="caratteri di contesto attorno a ogni entità")
    args = ap.parse_args()

    from backend.documenti import carica, info_ultimo_caricamento
    from backend.motore import anonimizza

    # Risolto subito: il percorso arriva dalla riga di comando e può essere
    # relativo, ma più sotto va confrontato con ROOT, che è assoluto.
    pdf = Path(args.pdf).resolve()
    print(f"documento: {pdf.name}")

    t0 = time.perf_counter()
    testo, _ = carica(str(pdf))
    t_carica = time.perf_counter() - t0
    info = info_ultimo_caricamento()

    pagine_ocr = info.get("ocr_pagine") or []
    totale_pag = info.get("ocr_totale", "?")
    print(f"estrazione: {t_carica:.1f}s — {len(testo):,} caratteri")
    print(f"pagine lette con OCR: {len(pagine_ocr)} su {totale_pag}  {pagine_ocr}")

    # In ``estratti/``, non accanto al PDF: il dump è il testo integrale di
    # un documento privato e deve restare in una cartella esclusa da git,
    # ma se sta insieme agli originali ``benchmark.utente`` lo rilegge come
    # se fosse un documento e conta due volte le stesse entità.
    dump = pdf.parent / "estratti" / (pdf.name + ".ocr.txt")
    dump.parent.mkdir(exist_ok=True)
    dump.write_text(testo, encoding="utf-8")
    mostrato = dump.relative_to(ROOT) if dump.is_relative_to(ROOT) else dump
    print(f"testo estratto salvato in: {mostrato}")

    t0 = time.perf_counter()
    _, entita = anonimizza(testo, f"verifica-ocr-{uuid.uuid4().hex[:8]}")
    t_analisi = time.perf_counter() - t0

    # I suggerimenti NON sono entità anonimizzate: hanno placeholder vuoto
    # e nella UI stanno nel riquadro "Possibili entità", da spuntare a mano.
    # Contarli insieme alle entità gonfia il totale di decine di voci e fa
    # sembrare un disastro quello che è solo un elenco di proposte.
    anonimizzate = [e for e in entita if not e.get("suggerito")]
    suggerite = [e for e in entita if e.get("suggerito")]
    print(f"analisi: {t_analisi:.1f}s — {len(anonimizzate)} entità anonimizzate, "
          f"{len(suggerite)} suggerimenti\n")

    def elenca(titolo: str, voci: list) -> None:
        print("=" * 100)
        print(titolo)
        print("=" * 100)
        for i, e in enumerate(voci, 1):
            valore = e["valore_reale"]
            print(f"[{i:3d}] {e['tipo']:<14} {valore!r}   ({e['occorrenze']} occ.)")
            posizioni = [m.start() for m in re.finditer(re.escape(valore), testo)]
            for pos in posizioni[:MAX_OCCORRENZE_MOSTRATE]:
                print(f"      {_contesto(testo, pos, pos + len(valore), args.contesto)}")
            if len(posizioni) > MAX_OCCORRENZE_MOSTRATE:
                print(f"      (+{len(posizioni) - MAX_OCCORRENZE_MOSTRATE} altre "
                      "occorrenze)")
            if not posizioni:
                print("      [!] valore non ritrovato nel testo — normalizzazione")

    elenca("ENTITÀ ANONIMIZZATE — sostituite nel testo in uscita", anonimizzate)
    elenca("SUGGERIMENTI — non sostituiti, proposti all'utente", suggerite)
    print("=" * 100)
    print(f"TOTALE: {len(anonimizzate)} anonimizzate + {len(suggerite)} suggerite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
