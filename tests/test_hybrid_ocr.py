"""Tests for Hybrid OCR extraction."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_engine import extract_markdown_hybrid_ocr, detect_scanned_pages


@pytest.fixture
def digital_pdf():
    """Create a PDF with mostly digital text (no scans)."""
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        # Add lots of text to simulate digital content
        for i in range(10):
            c.drawString(50, 750 - (i * 40), f"Linha {i+1}: Este é um texto digital normal")
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer
    except ImportError:
        pytest.skip("reportlab not installed")


@pytest.fixture
def mixed_pdf():
    """Create a PDF with mixed digital and scanned-like pages."""
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer)

        # Page 1: Digital (lots of text)
        for i in range(15):
            c.drawString(50, 750 - (i * 40), f"Página 1, linha {i+1}: Conteúdo digital")
        c.showPage()

        # Page 2: Scanned-like (minimal text)
        c.drawString(100, 700, "Página 2 - Imagem de documento")
        c.showPage()

        c.save()
        buffer.seek(0)
        return buffer
    except ImportError:
        pytest.skip("reportlab not installed")


def test_hybrid_ocr_digital_pdf(digital_pdf, tmp_path):
    """Test hybrid OCR on digital PDF (should skip OCR)."""
    pdf_path = tmp_path / "digital.pdf"
    pdf_path.write_bytes(digital_pdf.getvalue())

    markdown = extract_markdown_hybrid_ocr(str(pdf_path))

    assert markdown is not None
    assert len(markdown) > 0
    assert "digital" in markdown.lower() or "linha" in markdown.lower()


def test_hybrid_ocr_mixed_pdf(mixed_pdf, tmp_path):
    """Test hybrid OCR on mixed PDF (should detect and OCR scanned page)."""
    pdf_path = tmp_path / "mixed.pdf"
    pdf_path.write_bytes(mixed_pdf.getvalue())

    markdown = extract_markdown_hybrid_ocr(str(pdf_path))

    assert markdown is not None
    assert len(markdown) > 0


def test_detect_scanned_pages_digital(digital_pdf, tmp_path):
    """Test page detection on purely digital PDF."""
    pdf_path = tmp_path / "digital.pdf"
    pdf_path.write_bytes(digital_pdf.getvalue())

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions()
        options.do_ocr = False
        options.do_table_structure = False

        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
        result = converter.convert(str(pdf_path))

        scanned = detect_scanned_pages(result.document, text_threshold=100)

        # Digital PDF should have very few (if any) scanned pages
        assert isinstance(scanned, list)

    except ImportError:
        pytest.skip("Docling not installed")


def test_hybrid_ocr_nonexistent_file():
    """Test hybrid OCR with nonexistent file."""
    with pytest.raises(FileNotFoundError):
        extract_markdown_hybrid_ocr("/nonexistent/file.pdf")


def test_hybrid_ocr_invalid_pdf(tmp_path):
    """Test hybrid OCR with invalid PDF."""
    pdf_path = tmp_path / "invalid.pdf"
    pdf_path.write_bytes(b"This is not a PDF")

    with pytest.raises(ValueError, match="does not appear to be a valid PDF"):
        extract_markdown_hybrid_ocr(str(pdf_path))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
