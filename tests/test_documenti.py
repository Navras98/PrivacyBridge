# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Test dell'estrazione testo da PDF/DOCX/TXT/MD/CSV."""

from __future__ import annotations

import pytest

from backend.documenti import (
    DocumentoError,
    DocumentoScansionato,
    carica,
    carica_csv,
    carica_docx,
    carica_eml,
    carica_html,
    carica_md,
    carica_odt,
    carica_pdf,
    carica_rtf,
    carica_txt,
    carica_xlsx,
)

# ---------------------------------------------------------------------------
# Helper: crea un PDF fittizio con reportlab (già disponibile via pdfplumber)
# ---------------------------------------------------------------------------

def _pdf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _make_pdf(path: str, testo: str) -> None:
    """Genera un PDF minimale valido con testo estraibile.

    Non usiamo reportlab (non installato): scriviamo un PDF 1.4 a mano
    con font Helvetica standard e un content stream per pagina.
    """
    righe = testo.split("\n")
    # Costruisco lo stream di testo (BT ... ET).
    content_lines = ["BT", "/F1 12 Tf", "50 750 Td"]
    for i, riga in enumerate(righe):
        content_lines.append(f"({_pdf_escape(riga)}) Tj")
        if i < len(righe) - 1:
            content_lines.append("0 -18 Td")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1")

    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
    )
    objects.append(
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
        + content + b"\nendstream"
    )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )

    buf = bytearray()
    buf += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref_off = len(buf)
    buf += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    buf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        buf += f"{off:010d} 00000 n \n".encode("ascii")
    buf += (
        b"trailer\n<< /Size " + str(len(objects) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_off).encode("ascii") + b"\n%%EOF\n"
    )
    with open(path, "wb") as f:
        f.write(buf)


def _make_docx(path: str, testo: str) -> None:
    from docx import Document

    doc = Document()
    for riga in testo.split("\n"):
        doc.add_paragraph(riga)
    doc.save(path)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def test_carica_pdf(tmp_path):
    pdf_path = str(tmp_path / "test.pdf")
    payload = "Nome: Mario Rossi\nEmail: mario.rossi@example.com"
    _make_pdf(pdf_path, payload)

    testo, nome = carica_pdf(pdf_path)
    assert nome == "test.pdf"
    assert "Mario Rossi" in testo
    assert "mario.rossi@example.com" in testo


def test_carica_pdf_via_dispatch(tmp_path):
    pdf_path = str(tmp_path / "documento.pdf")
    _make_pdf(pdf_path, "Contenuto del PDF: Luigi Bianchi 333-1234567")
    testo, nome = carica(pdf_path)
    assert nome == "documento.pdf"
    assert "Luigi Bianchi" in testo


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def test_carica_docx(tmp_path):
    docx_path = str(tmp_path / "test.docx")
    payload = "Nome: Anna Verdi\nCF: RSSMRA80A01H501U\nTelefono: +39 333 987654"
    _make_docx(docx_path, payload)

    testo, nome = carica_docx(docx_path)
    assert nome == "test.docx"
    assert "Anna Verdi" in testo
    assert "RSSMRA80A01H501U" in testo
    assert "+39 333 987654" in testo


# ---------------------------------------------------------------------------
# TXT / MD / CSV
# ---------------------------------------------------------------------------

def test_carica_txt(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("Nome: Giulia Neri\nEmail: giulia@example.com\n", encoding="utf-8")
    testo, nome = carica_txt(str(p))
    assert nome == "test.txt"
    assert "Giulia Neri" in testo
    assert "giulia@example.com" in testo


def test_carica_md(tmp_path):
    p = tmp_path / "note.md"
    p.write_text("# Note\n\n- Paolo Rossi\n- paolo@example.com\n", encoding="utf-8")
    testo, nome = carica_md(str(p))
    assert nome == "note.md"
    assert "Paolo Rossi" in testo
    assert "# Note" in testo


def test_carica_csv(tmp_path):
    p = tmp_path / "clienti.csv"
    p.write_text(
        "nome,email,telefono\n"
        "Mario Rossi,mario@example.com,+39 333 111\n"
        "Luigi Bianchi,luigi@example.com,+39 333 222\n",
        encoding="utf-8",
    )
    testo, nome = carica_csv(str(p))
    assert nome == "clienti.csv"
    assert "Mario Rossi" in testo
    assert "luigi@example.com" in testo


def test_dispatch_multipla(tmp_path):
    files = {
        "a.txt": "hello txt",
        "b.md":  "# hello md",
    }
    for fname, content in files.items():
        p = tmp_path / fname
        p.write_text(content, encoding="utf-8")
        testo, nome = carica(str(p))
        assert content in testo
        assert nome == fname


# ---------------------------------------------------------------------------
# File corrotto → errore gestito
# ---------------------------------------------------------------------------

def test_pdf_corrotto_errore_gestito(tmp_path):
    p = tmp_path / "corrotto.pdf"
    p.write_bytes(b"questo non e un PDF valido \x00\x01\x02")
    with pytest.raises(DocumentoError):
        carica_pdf(str(p))


def test_docx_corrotto_errore_gestito(tmp_path):
    p = tmp_path / "corrotto.docx"
    p.write_bytes(b"neanche uno zip valido")
    with pytest.raises(DocumentoError):
        carica_docx(str(p))


def test_txt_binario_errore_gestito(tmp_path):
    p = tmp_path / "binario.txt"
    p.write_bytes(b"\xff\xfe\x00\x00valido? no.")
    with pytest.raises(DocumentoError):
        carica_txt(str(p))


def test_file_non_esistente(tmp_path):
    with pytest.raises(DocumentoError):
        carica_pdf(str(tmp_path / "non_esiste.pdf"))
    with pytest.raises(DocumentoError):
        carica_docx(str(tmp_path / "non_esiste.docx"))
    with pytest.raises(DocumentoError):
        carica_txt(str(tmp_path / "non_esiste.txt"))
    with pytest.raises(DocumentoError):
        carica_csv(str(tmp_path / "non_esiste.csv"))


def test_estensione_non_supportata(tmp_path):
    p = tmp_path / "immagine.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(DocumentoError):
        carica(str(p))


# ---------------------------------------------------------------------------
# FASE 3 — formati aggiuntivi
# ---------------------------------------------------------------------------

def test_pdf_scansionato_solleva_errore_dedicato(tmp_path):
    """Un PDF con solo pagine vuote/immagini (zero testo estratto) deve
    dare ``DocumentoScansionato`` con messaggio chiaro."""
    p = tmp_path / "scan.pdf"
    # PDF con 1 pagina completamente vuota (nessun BT/ET stream).
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<<>>/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length 0>>stream\n\nendstream\nendobj\n"
        b"xref\n0 5\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000053 00000 n \n"
        b"0000000098 00000 n \n"
        b"0000000178 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>startxref\n220\n%%EOF"
    )
    p.write_bytes(pdf)
    with pytest.raises(DocumentoScansionato) as ei:
        carica_pdf(str(p))
    assert "scansione" in str(ei.value).lower()


def test_carica_eml(tmp_path):
    p = tmp_path / "prova.eml"
    contenuto = (
        b"From: Andrea <andrea@example.com>\n"
        b"To: mario@example.com\n"
        b"Subject: Preventivo\n"
        b"Date: Mon, 29 Jul 2026 09:00:00 +0200\n"
        b"Content-Type: text/plain; charset=utf-8\n"
        b"\n"
        b"Ciao Mario,\n"
        b"in allegato il preventivo.\n"
        b"Andrea\n"
    )
    p.write_bytes(contenuto)
    testo, nome = carica_eml(str(p))
    assert "Andrea" in testo
    assert "mario@example.com" in testo
    assert "Subject: Preventivo" in testo
    assert nome == "prova.eml"


def test_carica_rtf(tmp_path):
    p = tmp_path / "prova.rtf"
    rtf = (
        r"{\rtf1\ansi\deff0 {\fonttbl {\f0 Times New Roman;}}"
        r"\f0\fs24 Ciao \b Andrea\b0 , in allegato il preventivo.}"
    ).encode("cp1252")
    p.write_bytes(rtf)
    testo, _ = carica_rtf(str(p))
    assert "Andrea" in testo
    assert "preventivo" in testo
    # No tag RTF residui.
    assert r"\rtf" not in testo
    assert r"\fonttbl" not in testo


def test_carica_odt(tmp_path):
    """Crea un ODT minimale via odfpy stesso."""
    from odf.opendocument import OpenDocumentText
    from odf.text import P

    p = tmp_path / "prova.odt"
    doc = OpenDocumentText()
    para = P(text="Il cliente Mario Rossi ha firmato il contratto.")
    doc.text.addElement(para)
    doc.save(str(p))
    testo, _ = carica_odt(str(p))
    assert "Mario Rossi" in testo


def test_carica_xlsx(tmp_path):
    from openpyxl import Workbook
    p = tmp_path / "prova.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Anagrafica"
    ws.append(["Nome", "Email", "Telefono"])
    ws.append(["Anna Verdi", "anna@example.com", "333 1234567"])
    ws.append(["Marco Neri", "marco@example.com", "339 9876543"])
    wb.save(str(p))
    testo, _ = carica_xlsx(str(p))
    assert "Anagrafica" in testo
    assert "Anna Verdi" in testo
    assert "anna@example.com" in testo
    assert "Marco Neri" in testo


def test_carica_html(tmp_path):
    p = tmp_path / "prova.html"
    html = (
        "<html><head><title>Test</title>"
        "<style>body{color:red}</style></head>"
        "<body>"
        "<p>Ciao <b>Andrea</b>, ecco il documento.</p>"
        "<script>alert('rumore')</script>"
        "<p>Cordiali saluti, Mario Rossi.</p>"
        "</body></html>"
    )
    p.write_text(html, encoding="utf-8")
    testo, _ = carica_html(str(p))
    assert "Andrea" in testo
    assert "Mario Rossi" in testo
    assert "<" not in testo
    assert "alert" not in testo  # script rimosso
    assert "color:red" not in testo  # style rimosso


def test_dispatch_include_nuovi_formati(tmp_path):
    """Il dispatch ``carica`` deve gestire i nuovi formati via estensione."""
    # eml
    p = tmp_path / "d.eml"
    p.write_bytes(b"Subject: X\n\nHello")
    testo, _ = carica(str(p))
    assert "Subject: X" in testo

    # html
    p2 = tmp_path / "d.htm"
    p2.write_text("<p>Ok</p>", encoding="utf-8")
    testo2, _ = carica(str(p2))
    assert "Ok" in testo2


# ---------------------------------------------------------------------------
# PARTE 2 — OCR nativo per PDF scansionati
# ---------------------------------------------------------------------------

def _pdf_immagine(tmp_path, testo: str):
    """Genera un PDF di sola immagine (nessun livello testo) che
    contiene ``testo`` renderizzato — simula una scansione."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1654, 2339), "white")   # ~A4 a 200 dpi
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except Exception:
        font = ImageFont.load_default()
    y = 200
    for riga in testo.split("\n"):
        draw.text((150, y), riga, fill="black", font=font)
        y += 90
    p = tmp_path / "scansione.pdf"
    img.save(str(p), "PDF", resolution=200)
    return str(p)


def test_pdf_scansionato_ocr_estrae_testo(tmp_path):
    """Un PDF di sola immagine con testo leggibile deve passare
    dall'OCR nativo e restituire il contenuto (macOS Vision)."""
    from backend.ocr import ocr_disponibile

    if not ocr_disponibile():
        pytest.skip("OCR nativo non disponibile su questa macchina")

    contenuto = (
        "Il sottoscritto Mario Rossi, nato ad Assisi,\n"
        "codice fiscale RSSMRA85T10A944I,\n"
        "chiede il rilascio del documento."
    )
    p = _pdf_immagine(tmp_path, contenuto)
    testo, _ = carica_pdf(p)
    assert "Mario Rossi" in testo
    # Confronto case-insensitive: Vision confonde I/l a fine codice
    # ("…A944I" letto "…A944l") — è il limite OCR documentato in UI
    # ("un CF letto male non supera più il controllo di validità").
    assert "RSSMRA85T10A944".lower() in testo.lower()

    from backend.documenti import info_ultimo_caricamento
    info = info_ultimo_caricamento()
    assert info.get("ocr_pagine") == [1]


def _scrivi_pdf_testuale(path, testo: str) -> None:
    """PDF minimale con un vero livello di testo (stream BT/ET)."""
    from pathlib import Path as _P
    righe = []
    while testo:
        righe.append(testo[:80])
        testo = testo[80:]
    contenuto = "BT /F1 10 Tf 40 750 Td 12 TL " + " ".join(
        f"({r}) Tj T*" for r in righe
    ) + " ET"
    stream = contenuto.encode("latin-1")
    corpo = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        b"/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length " + str(len(stream)).encode() + b">>stream\n"
        + stream + b"\nendstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"trailer<</Size 6/Root 1 0 R>>\n%%EOF"
    )
    _P(path).write_bytes(corpo)


def test_pdf_misto_solo_pagine_povere_in_ocr(tmp_path):
    """In un PDF misto l'OCR tocca solo le pagine povere di testo con
    immagine dominante: le pagine testuali restano com'erano."""
    from backend.ocr import ocr_disponibile

    if not ocr_disponibile():
        pytest.skip("OCR nativo non disponibile su questa macchina")

    import pypdfium2 as pdfium

    # Pagina scansione (immagine con testo) + pagina di testo ricco
    # (>600 char, nessuna immagine) fuse in un unico PDF.
    p_scan = _pdf_immagine(tmp_path, "Contattare Luigi Bianchi al 3391234567")
    p_testo = tmp_path / "solo_testo.pdf"
    _scrivi_pdf_testuale(p_testo, "Relazione tecnica. " * 60)

    dest = pdfium.PdfDocument.new()
    for sorgente in (p_scan, str(p_testo)):
        src = pdfium.PdfDocument(sorgente)
        dest.import_pages(src)
        src.close()
    p_misto = tmp_path / "misto.pdf"
    dest.save(str(p_misto))
    dest.close()

    testo, _ = carica_pdf(str(p_misto))
    assert "Luigi Bianchi" in testo          # dalla pagina OCR
    assert "Relazione tecnica." in testo     # dalla pagina testuale

    from backend.documenti import info_ultimo_caricamento
    info = info_ultimo_caricamento()
    assert info.get("ocr_pagine") == [1]     # SOLO la pagina scansione
    assert info.get("ocr_totale") == 2
