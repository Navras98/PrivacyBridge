# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Confronta le impostazioni dell'OCR di sistema su un PDF scansionato.

Sul documento scansionato dell'utente il motore lascia in chiaro tre
e-mail e quattro sequenze tipo carta: non perché non le cerchi, ma perché
l'OCR le consegna rotte — uno spazio prima della chiocciola, una cifra
sbagliata che fa fallire Luhn.  Prima di scrivere correzioni a valle
conviene sapere se il difetto si può togliere a monte, e quanto costa.

Quattro varianti sulle stesse pagine, con la stessa pipeline di
rilevamento a valle:

  attuale        220 DPI, livello accurato, correzione linguistica accesa
  dpi300         come sopra ma a 300 DPI
  senza_lingua   correzione linguistica spenta — l'ipotesi è che sia lei
                 a "correggere" gli indirizzi verso parole italiane
  candidati      tiene le prime tre ipotesi di Vision invece della sola
                 migliore, e sceglie quella che supera un checksum

Per ogni variante: caratteri estratti, entità trovate, dati rimasti in
chiaro, secondi.  Il confronto è sul testo dell'utente, non su esempi.

Uso:
    venv/bin/python -m benchmark.ocr_opzioni "benchmark/documenti_utente/Indagine .pdf"
    venv/bin/python -m benchmark.ocr_opzioni <pdf> --pagine 0,1,2,3,4
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from benchmark import CATEGORIE_CONSEGNA, isola, vault_isolato
from benchmark.audit_precisione import RESIDUI, _luhn, _maschera_segnaposto

isola("ocr")

VAULT_DB = vault_isolato("ocr")


def _rasterizza(pdf_path: str, indice: int, dpi: int) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        img = pdf[indice].render(scale=dpi / 72.0).to_pil()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        pdf.close()


def _ocr(png: bytes, *, lingua: bool, n_candidati: int) -> str:
    """OCR con Vision, esponendo le due manopole che l'app non usa."""
    import Foundation
    import Vision

    dati = Foundation.NSData.dataWithBytes_length_(png, len(png))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(dati, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setRecognitionLanguages_(["it-IT", "en-US"])
    req.setUsesLanguageCorrection_(lingua)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision OCR fallito: {err}")

    righe = []
    for oss in req.results() or []:
        cands = oss.topCandidates_(n_candidati)
        if not cands or not len(cands):
            continue
        scelta = str(cands[0].string())
        if n_candidati > 1:
            # Fra le ipotesi alternative vince quella che contiene una
            # sequenza numerica valida secondo Luhn: se Vision ha esitato
            # su una cifra, l'aritmetica dice quale delle due aveva ragione.
            for k in range(len(cands)):
                testo = str(cands[k].string())
                cifre = "".join(c for c in testo if c.isdigit())
                if len(cifre) >= 13 and _luhn(cifre):
                    scelta = testo
                    break
        righe.append(scelta)
    return "\n".join(righe)


def _residui(out: str) -> list[tuple[str, str]]:
    pulito = _maschera_segnaposto(out)
    fuori = []
    for nome, rx in RESIDUI.items():
        if nome not in ("email", "sequenza_carta", "codice_fiscale", "iban"):
            continue
        for m in rx.finditer(pulito):
            v = m.group(0).strip()
            if v and (nome, v) not in fuori:
                fuori.append((nome, v))
    return fuori


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf")
    ap.add_argument("--pagine", help="indici 0-based separati da virgola (default: tutte)")
    args = ap.parse_args()

    pdf = Path(args.pdf).resolve()
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    totale = len(doc)
    doc.close()
    pagine = (
        [int(x) for x in args.pagine.split(",")] if args.pagine else list(range(totale))
    )

    from backend.motore import anonimizza, reset_analyzer
    reset_analyzer()
    cat = set(CATEGORIE_CONSEGNA)

    varianti = [
        ("attuale",      {"dpi": 220, "lingua": True,  "n_candidati": 1}),
        ("dpi300",       {"dpi": 300, "lingua": True,  "n_candidati": 1}),
        ("senza_lingua", {"dpi": 220, "lingua": False, "n_candidati": 1}),
        ("candidati",    {"dpi": 220, "lingua": True,  "n_candidati": 3}),
    ]

    print(f"documento: {pdf.name} — {len(pagine)} pagine su {totale}\n", flush=True)
    esiti = []
    for nome, cfg in varianti:
        t0 = time.perf_counter()
        pezzi = []
        for i in pagine:
            png = _rasterizza(str(pdf), i, cfg["dpi"])
            pezzi.append(_ocr(png, lingua=cfg["lingua"], n_candidati=cfg["n_candidati"]))
        testo = "\n".join(pezzi)
        t_ocr = time.perf_counter() - t0

        out, ents = anonimizza(testo, f"ocr-{nome}", db_path=VAULT_DB, categorie_attive=cat)
        attive = [e for e in ents if not e.get("suggerito") and e.get("placeholder")]
        res = _residui(out)
        esiti.append((nome, len(testo), len(attive), res, t_ocr))
        dump = ROOT / "benchmark" / "documenti_utente" / "estratti" / f"{pdf.stem}.{nome}.txt"
        dump.parent.mkdir(exist_ok=True)
        dump.write_text(testo, encoding="utf-8")
        print(f"{nome:<14} {len(testo):>7,} car  {len(attive):>4} entità  "
              f"{len(res):>3} residui  {t_ocr:>6.1f}s", flush=True)

    print("\n" + "=" * 78)
    print("DATI RIMASTI IN CHIARO, PER VARIANTE")
    print("=" * 78)
    for nome, _car, _n, res, _t in esiti:
        print(f"\n[{nome}] {len(res)} residui")
        for schema, valore in sorted(res):
            print(f"    {schema:<16} {valore!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
