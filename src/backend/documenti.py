# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Estrazione testo da documenti.

Formati supportati (FASE 3 in corso):
  PDF, DOCX, TXT, MD, CSV, EML, MSG, RTF, ODT, XLSX, HTML.

Convenzione: ogni ``carica_*`` ritorna ``(testo, nome_file)`` oppure
solleva ``DocumentoError`` con messaggio in italiano.

PDF scansionati: se il testo estratto è sotto una soglia rispetto al
numero di pagine, ``DocumentoError`` con messaggio esplicito che dice
"questo PDF è probabilmente una scansione". Nessun OCR incorporato
(vedi BLOCCHI.md).
"""

from __future__ import annotations

import csv
import io
import os
import re
from email import policy
from email.parser import BytesParser
from pathlib import Path


class DocumentoError(Exception):
    """Errore gestito in fase di estrazione testo."""


class DocumentoScansionato(DocumentoError):
    """Errore specifico: PDF che sembra una scansione (poco/nessun testo)."""


def _nome(path: str) -> str:
    return os.path.basename(path)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

# Soglia caratteri sotto la quale sospettiamo una scansione.
# Conservativa: un PDF di test/breve può avere 40-80 char totali; una
# scansione tipica ne ha 0. Scattiamo solo su casi molto evidenti.
_PDF_SCAN_CHAR_TOTALE = 20                 # < 20 char su TUTTO il PDF
_PDF_SCAN_CHAR_PER_PAGINA_MULTIPAG = 15    # o media < 15 char/pag su >= 3 pagine

# Regola OCR per-pagina (PDF misti): una pagina va ri-letta con l'OCR
# nativo se il testo incorporato è scarso E un'immagine copre gran
# parte della pagina. Copre i PDF con livello OCR incorporato di
# scarsa qualità (55 char su una pagina interamente scansionata) e le
# pagine-fotografia in mezzo a un documento testuale.
_PDF_OCR_CHAR_PAGINA = 600      # testo incorporato "scarso"
_PDF_OCR_COPERTURA_IMG = 0.5    # immagini > 50% dell'area pagina

# Metadati dell'ultimo caricamento (letti dall'API per informare la UI
# che alcune pagine sono passate dall'OCR → rilevamento meno affidabile).
_info_ultimo: dict = {}


def info_ultimo_caricamento() -> dict:
    """Metadati dell'ultimo documento caricato (es. pagine OCR)."""
    return dict(_info_ultimo)


def _copertura_immagini(pagina) -> float:
    """Frazione [0..1] dell'area pagina coperta da immagini."""
    area = float(pagina.width) * float(pagina.height)
    if area <= 0:
        return 0.0
    tot = 0.0
    for im in pagina.images:
        tot += max(0.0, (im["x1"] - im["x0"])) * max(0.0, (im["bottom"] - im["top"]))
    return min(1.0, tot / area)


def carica_pdf(path: str) -> tuple[str, str]:
    """Estrae il testo da un PDF usando pdfplumber, con OCR nativo di
    sistema per le pagine scansionate.

    Regole:
      1. Pagina con testo scarso (<600 char) e immagine dominante
         (>50% area) → rasterizzata e passata all'OCR; si tiene il
         testo più lungo fra incorporato e OCR.
      2. Documento interamente scansionato (soglia storica: <20 char
         totali o <15 char/pag su ≥3 pagine) → OCR di tutte le pagine.
      3. OCR nativo non disponibile → ``DocumentoScansionato`` con
         messaggio esplicito (comportamento precedente).
    """
    import pdfplumber

    global _info_ultimo
    _info_ultimo = {}

    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    parti: list[str] = []
    coperture: list[float] = []
    n_pagine = 0
    try:
        with pdfplumber.open(path) as pdf:
            n_pagine = len(pdf.pages)
            for pagina in pdf.pages:
                testo = pagina.extract_text() or ""
                parti.append(testo)
                coperture.append(_copertura_immagini(pagina))
    except Exception as exc:
        raise DocumentoError(f"PDF non leggibile ({path}): {exc}") from exc

    char_totali = sum(len(s) for s in parti)
    media = (char_totali / n_pagine) if n_pagine else 0.0
    e_scansione = n_pagine > 0 and (
        char_totali < _PDF_SCAN_CHAR_TOTALE
        or (n_pagine >= 3 and media < _PDF_SCAN_CHAR_PER_PAGINA_MULTIPAG)
    )

    # Selezione pagine da mandare all'OCR.
    if e_scansione:
        da_ocr = list(range(n_pagine))
    else:
        da_ocr = [
            i for i in range(n_pagine)
            if len(parti[i]) < _PDF_OCR_CHAR_PAGINA
            and coperture[i] > _PDF_OCR_COPERTURA_IMG
        ]

    if da_ocr:
        from .ocr import ocr_disponibile, ocr_pagine_pdf

        if not ocr_disponibile():
            if e_scansione:
                raise DocumentoScansionato(
                    "Il PDF sembra una scansione (immagine) e non contiene "
                    f"testo leggibile: {char_totali} caratteri su {n_pagine} "
                    f"pagine ({media:.0f} car/pag). L'OCR nativo del sistema "
                    "non è disponibile su questa macchina: serve un OCR "
                    "esterno (Anteprima di macOS: Strumenti → Testo "
                    "effettivo, oppure Adobe Acrobat)."
                )
            # PDF misto ma OCR non disponibile: prosegui col solo testo
            # incorporato (meglio un'estrazione parziale che un errore).
        else:
            risultati = ocr_pagine_pdf(str(p), da_ocr, n_pagine, _nome(path))
            pagine_ocr: list[int] = []
            for i, testo_ocr in risultati.items():
                if len(testo_ocr) > len(parti[i]):
                    parti[i] = testo_ocr
                    pagine_ocr.append(i + 1)
            if pagine_ocr:
                _info_ultimo = {
                    "ocr_pagine": sorted(pagine_ocr),
                    "ocr_totale": n_pagine,
                }

    testo_full = "\n".join(parti)
    char_finali = sum(len(s) for s in parti)

    # Anche dopo l'OCR non c'è testo: il documento è illeggibile.
    if n_pagine > 0 and char_finali < _PDF_SCAN_CHAR_TOTALE:
        raise DocumentoScansionato(
            "Il PDF è una scansione e nemmeno l'OCR è riuscito a "
            f"estrarre testo leggibile ({char_finali} caratteri su "
            f"{n_pagine} pagine). Verifica la qualità della scansione."
        )

    return testo_full, _nome(path)


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def carica_docx(path: str) -> tuple[str, str]:
    """Estrae il testo da un DOCX usando python-docx."""
    from docx import Document

    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    try:
        doc = Document(path)
    except Exception as exc:
        raise DocumentoError(f"DOCX non leggibile ({path}): {exc}") from exc
    parti = [para.text for para in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parti.append("\t".join(cell.text for cell in row.cells))
    return "\n".join(parti), _nome(path)


# ---------------------------------------------------------------------------
# TXT / MD
# ---------------------------------------------------------------------------

def carica_txt(path: str) -> tuple[str, str]:
    """Legge un file di testo (TXT/MD). Tenta UTF-8, poi CP1252.

    ``latin-1`` accetterebbe qualunque byte silenziosamente e
    trasformerebbe un file binario in "testo" muto; per evitare falsi
    successi, dopo il decode contiamo i caratteri di controllo — se
    troppi, dichiariamo il file binario.
    """
    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise DocumentoError(f"Impossibile leggere {path}: {exc}") from exc
    for enc in ("utf-8", "cp1252"):
        try:
            testo = raw.decode(enc)
            if _sembra_binario(testo):
                raise DocumentoError(
                    f"Il file sembra binario, non testo leggibile: {path}"
                )
            return testo, _nome(path)
        except UnicodeDecodeError:
            continue
    raise DocumentoError(f"Encoding non riconosciuto per {path}")


# Oltre questa frazione di caratteri di controllo il file non è testo:
# è un binario aperto con l'encoding sbagliato. Il margine serve perché
# qualche documento vero contiene un form feed o un carattere di
# tabulazione esotico senza per questo essere illeggibile.
_MAX_FRAZIONE_CONTROLLO = 0.05


def _sembra_binario(testo: str) -> bool:
    """True se ``testo`` contiene troppi caratteri di controllo per
    essere plausibilmente testo umano."""
    if not testo:
        return False
    n_control = sum(
        1
        for c in testo
        if ord(c) < 32 and c not in "\n\t\r"
    )
    return n_control / len(testo) > _MAX_FRAZIONE_CONTROLLO


def carica_md(path: str) -> tuple[str, str]:
    return carica_txt(path)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def carica_csv(path: str) -> tuple[str, str]:
    """CSV: rappresentazione testuale, delimitatore auto-rilevato."""
    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise DocumentoError(f"Impossibile leggere {path}: {exc}") from exc
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise DocumentoError(f"Encoding non riconosciuto per {path}")

    dialect = None
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t|")
    except csv.Error:
        pass
    reader = csv.reader(io.StringIO(text), dialect=dialect) if dialect \
        else csv.reader(io.StringIO(text))
    buf = io.StringIO()
    for row in reader:
        buf.write(", ".join(row) + "\n")
    return buf.getvalue(), _nome(path)


# ---------------------------------------------------------------------------
# EML (email standard)
# ---------------------------------------------------------------------------

def carica_eml(path: str) -> tuple[str, str]:
    """Estrae ``From``, ``To``, ``Subject``, ``Date`` + body plain-text.

    Se il body è HTML lo passa a ``carica_html`` (rimuove i tag).
    """
    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    try:
        with p.open("rb") as fh:
            msg = BytesParser(policy=policy.default).parse(fh)
    except Exception as exc:
        raise DocumentoError(f"EML non leggibile ({path}): {exc}") from exc

    headers = []
    for h in ("From", "To", "Cc", "Subject", "Date"):
        v = msg.get(h)
        if v:
            headers.append(f"{h}: {v}")

    # Estrai body: preferisce text/plain, ripiega su text/html strippato.
    body = ""
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is not None:
            content = part.get_content()
            if part.get_content_type() == "text/html":
                body = _html_a_testo(content)
            else:
                body = content
    except Exception:
        body = ""

    testo = "\n".join(headers) + ("\n\n" + body if body else "")
    return testo, _nome(path)


# ---------------------------------------------------------------------------
# MSG (Outlook)
# ---------------------------------------------------------------------------

def carica_msg(path: str) -> tuple[str, str]:
    """MSG di Outlook via extract-msg."""
    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    try:
        import extract_msg
    except ImportError as exc:
        raise DocumentoError(
            "Modulo 'extract_msg' non installato. Non posso leggere file .msg."
        ) from exc
    try:
        m = extract_msg.Message(path)
    except Exception as exc:
        raise DocumentoError(f"MSG non leggibile ({path}): {exc}") from exc
    try:
        headers = []
        for etichetta, val in (
            ("From", m.sender),
            ("To", m.to),
            ("Cc", m.cc),
            ("Subject", m.subject),
            ("Date", m.date),
        ):
            if val:
                headers.append(f"{etichetta}: {val}")
        body = m.body or ""
        testo = "\n".join(headers) + ("\n\n" + body if body else "")
        return testo, _nome(path)
    finally:
        try:
            m.close()
        except OSError:
            # Il testo è già stato estratto: un handle che non si chiude
            # non deve trasformare una lettura riuscita in un errore.
            pass


# ---------------------------------------------------------------------------
# RTF
# ---------------------------------------------------------------------------

def carica_rtf(path: str) -> tuple[str, str]:
    """RTF via striprtf: rimuove i tag di formattazione."""
    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError as exc:
        raise DocumentoError("Modulo 'striprtf' non installato.") from exc
    try:
        raw = p.read_bytes()
        # RTF è ASCII con escape per unicode: tentiamo UTF-8 con
        # fallback su CP1252/Latin-1 per compatibilità con Word.
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise DocumentoError(f"RTF: encoding non riconosciuto per {path}")
        return rtf_to_text(text, errors="ignore"), _nome(path)
    except DocumentoError:
        raise
    except Exception as exc:
        raise DocumentoError(f"RTF non leggibile ({path}): {exc}") from exc


# ---------------------------------------------------------------------------
# ODT (OpenDocument Text)
# ---------------------------------------------------------------------------

def carica_odt(path: str) -> tuple[str, str]:
    """ODT via odfpy."""
    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    try:
        from odf.opendocument import load as odf_load
        from odf.table import TableCell, TableRow
        from odf.text import H, P
    except ImportError as exc:
        raise DocumentoError("Modulo 'odfpy' non installato.") from exc
    try:
        doc = odf_load(path)
    except Exception as exc:
        raise DocumentoError(f"ODT non leggibile ({path}): {exc}") from exc
    parti = []
    for elem in doc.getElementsByType(P) + doc.getElementsByType(H):
        parti.append(_odf_testo(elem))
    for row in doc.getElementsByType(TableRow):
        cells = row.getElementsByType(TableCell)
        parti.append("\t".join(_odf_testo(c) for c in cells))
    return "\n".join(t for t in parti if t is not None), _nome(path)


def _odf_testo(elem) -> str:
    """Concatena il testo di un elemento ODF (foglio + figli)."""
    parts = []
    for node in elem.childNodes:
        if node.nodeType == 3:  # TEXT_NODE
            parts.append(node.data)
        else:
            parts.append(_odf_testo(node))
    return "".join(parts)


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------

def carica_xlsx(path: str) -> tuple[str, str]:
    """XLSX via openpyxl: ogni foglio come sezione, righe come CSV."""
    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise DocumentoError("Modulo 'openpyxl' non installato.") from exc
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise DocumentoError(f"XLSX non leggibile ({path}): {exc}") from exc
    try:
        sezioni = []
        for nome_foglio in wb.sheetnames:
            ws = wb[nome_foglio]
            righe = []
            for row in ws.iter_rows(values_only=True):
                celle = ["" if v is None else str(v) for v in row]
                # Salta righe interamente vuote.
                if any(c.strip() for c in celle):
                    righe.append(", ".join(celle))
            if righe:
                sezioni.append(f"# Foglio: {nome_foglio}\n" + "\n".join(righe))
        return "\n\n".join(sezioni), _nome(path)
    finally:
        wb.close()


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def carica_html(path: str) -> tuple[str, str]:
    """HTML: strip dei tag via BeautifulSoup, restituisce testo pulito."""
    p = Path(path)
    if not p.is_file():
        raise DocumentoError(f"File non trovato: {path}")
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise DocumentoError(f"Impossibile leggere {path}: {exc}") from exc
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            html_text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise DocumentoError(f"HTML: encoding non riconosciuto per {path}")
    return _html_a_testo(html_text), _nome(path)


def _html_a_testo(html_text: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Ripiego molto grezzo: strip di tag via regex.
        return re.sub(r"<[^>]+>", " ", html_text)
    soup = BeautifulSoup(html_text, "html.parser")
    # Rimuovi script/style che contengono rumore.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    # Preserva la struttura minima (paragrafi/br).
    testo = soup.get_text(separator="\n")
    # Comprimi whitespace multipli.
    testo = re.sub(r"\n{3,}", "\n\n", testo)
    testo = re.sub(r"[ \t]+", " ", testo)
    return testo.strip()


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_HANDLERS = {
    ".pdf": carica_pdf,
    ".docx": carica_docx,
    ".txt": carica_txt,
    ".md": carica_md,
    ".markdown": carica_md,
    ".csv": carica_csv,
    ".eml": carica_eml,
    ".msg": carica_msg,
    ".rtf": carica_rtf,
    ".odt": carica_odt,
    ".xlsx": carica_xlsx,
    ".html": carica_html,
    ".htm": carica_html,
}


ESTENSIONI_SUPPORTATE = tuple(sorted(_HANDLERS.keys()))


def carica(path: str) -> tuple[str, str]:
    """Dispatch in base all'estensione del file."""
    ext = Path(path).suffix.lower()
    handler = _HANDLERS.get(ext)
    if handler is None:
        raise DocumentoError(
            f"Estensione non supportata: {ext}. "
            f"Formati ammessi: {', '.join(ESTENSIONI_SUPPORTATE)}."
        )
    return handler(path)
