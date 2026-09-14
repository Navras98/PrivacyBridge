# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""OCR nativo del sistema operativo per PDF scansionati.

- macOS: framework Vision (``VNRecognizeTextRequest``) via pyobjc.
  Integrato nel sistema, gratuito, ottimo sull'italiano, zero
  dipendenze pesanti aggiunte al pacchetto.
- Windows: ``Windows.Media.Ocr`` via ``winsdk`` (ramo presente ma MAI
  provato su Windows reale — vedi BLOCCHI.md).
- Altrimenti: ``ocr_disponibile()`` è False e il chiamante mostra il
  messaggio "serve un OCR esterno".

La rasterizzazione delle pagine PDF usa pypdfium2 (già dipendenza di
pdfplumber): nessuna dipendenza nuova.

Avanzamento: lo stato corrente è esposto in ``stato_ocr()`` — la UI lo
interroga in polling durante il caricamento per mostrare "Documento
scansionato: pagina 3 di 12".
"""

from __future__ import annotations

import logging
import sys
import threading

logger = logging.getLogger("privacybridge.ocr")

_DPI = 220   # compromesso qualità/velocità per scansioni A4


# ---------------------------------------------------------------------------
# Stato di avanzamento (per la UI)
# ---------------------------------------------------------------------------

_stato_lock = threading.Lock()
_stato = {"attivo": False, "pagina": 0, "totale": 0, "file": ""}


def stato_ocr() -> dict:
    with _stato_lock:
        return dict(_stato)


def _aggiorna_stato(**kv) -> None:
    with _stato_lock:
        _stato.update(kv)


# ---------------------------------------------------------------------------
# Disponibilità
# ---------------------------------------------------------------------------

_disponibile_cache: bool | None = None


def ocr_disponibile() -> bool:
    """True se l'OCR nativo del sistema operativo è utilizzabile."""
    global _disponibile_cache
    if _disponibile_cache is not None:
        return _disponibile_cache
    if sys.platform == "darwin":
        try:
            import Vision  # noqa: F401
            _disponibile_cache = True
        except Exception:
            _disponibile_cache = False
    elif sys.platform == "win32":
        try:
            from winsdk.windows.media.ocr import OcrEngine
            _disponibile_cache = OcrEngine.try_create_from_user_profile_languages() is not None
        except Exception:
            _disponibile_cache = False
    else:
        _disponibile_cache = False
    return _disponibile_cache


# ---------------------------------------------------------------------------
# Rasterizzazione (pypdfium2)
# ---------------------------------------------------------------------------

def _rasterizza_pagina_png(pdf_path: str, indice: int, dpi: int = _DPI) -> bytes:
    """Rasterizza la pagina ``indice`` (0-based) in PNG."""
    import io

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        pagina = pdf[indice]
        bitmap = pagina.render(scale=dpi / 72.0)
        img = bitmap.to_pil()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        pdf.close()


# ---------------------------------------------------------------------------
# OCR di una singola immagine
# ---------------------------------------------------------------------------

def _ocr_png_macos(png: bytes) -> str:
    import Foundation
    import Vision

    dati = Foundation.NSData.dataWithBytes_length_(png, len(png))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(dati, None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["it-IT", "en-US"])
    request.setUsesLanguageCorrection_(True)
    ok, err = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision OCR fallito: {err}")
    righe = []
    for oss in request.results() or []:
        candidati = oss.topCandidates_(1)
        if candidati and len(candidati):
            righe.append(str(candidati[0].string()))
    return "\n".join(righe)


def _ocr_png_windows(png: bytes) -> str:  # pragma: no cover — mai provato su Windows
    import asyncio

    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.storage.streams import (
        DataWriter,
        InMemoryRandomAccessStream,
    )

    async def _run() -> str:
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream.get_output_stream_at(0))
        writer.write_bytes(png)
        await writer.store_async()
        decoder = await BitmapDecoder.create_async(stream)
        bmp = await decoder.get_software_bitmap_async()
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("Nessuna lingua OCR installata in Windows")
        result = await engine.recognize_async(bmp)
        return "\n".join(line.text for line in result.lines)

    return asyncio.run(_run())


def ocr_png(png: bytes) -> str:
    """OCR di un'immagine PNG con il motore nativo della piattaforma."""
    if sys.platform == "darwin":
        return _ocr_png_macos(png)
    if sys.platform == "win32":
        return _ocr_png_windows(png)
    raise RuntimeError("OCR nativo non disponibile su questa piattaforma")


# ---------------------------------------------------------------------------
# OCR di pagine PDF
# ---------------------------------------------------------------------------

def ocr_pagine_pdf(
    pdf_path: str,
    indici: list[int],
    totale_pagine: int,
    nome_file: str = "",
) -> dict[int, str]:
    """OCR delle pagine ``indici`` (0-based) di ``pdf_path``.

    Ritorna ``{indice: testo}``. Aggiorna lo stato di avanzamento per
    la UI. Gli errori su una singola pagina non fermano le altre.
    """
    out: dict[int, str] = {}
    _aggiorna_stato(attivo=True, pagina=0, totale=len(indici), file=nome_file)
    try:
        for n, i in enumerate(indici, start=1):
            _aggiorna_stato(pagina=n)
            try:
                png = _rasterizza_pagina_png(pdf_path, i)
                out[i] = ocr_png(png)
            except Exception as exc:
                logger.warning("OCR pagina %d/%d fallito: %s", i + 1, totale_pagine, exc)
                out[i] = ""
    finally:
        _aggiorna_stato(attivo=False, pagina=0, totale=0, file="")
    return out
