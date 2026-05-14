"""PDF extraction helpers."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def _validate_pdf(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"File does not have a .pdf extension: {path.name}")
    # Check PDF magic bytes (%PDF-)
    with path.open("rb") as f:
        header = f.read(5)
    if header != b"%PDF-":
        raise ValueError(f"File does not appear to be a valid PDF: {path.name}")


def pdf_info(pdf_path: str | Path) -> dict[str, Any]:
    path = Path(pdf_path)
    _validate_pdf(path)
    reader = PdfReader(str(path))
    return {
        "nome": path.name,
        "tamanho_bytes": path.stat().st_size,
        "paginas_totais": len(reader.pages),
        "criptografado": reader.is_encrypted,
        "metadados": dict(reader.metadata or {}),
    }


def extract_page_texts(pdf_path: str | Path) -> list[str]:
    path = Path(pdf_path)
    _validate_pdf(path)
    reader = PdfReader(str(path))
    texts = []
    for i, page in enumerate(reader.pages):
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            logger.warning("Failed to extract text from page %d, skipping.", i + 1)
            texts.append("")
    return texts


def extract_markdown_docling(pdf_path: str | Path) -> str:
    """Extract Markdown from PDF via Docling. Falls back to pypdf plain text on failure."""
    path = Path(pdf_path)
    _validate_pdf(path)

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        start_time = time.time()

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = False

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
        result = converter.convert(str(path))
        markdown = result.document.export_to_markdown()

        elapsed = time.time() - start_time
        logger.info("Docling extraction successful: %d chars (%.1f seconds)",
                   len(markdown), elapsed)
        return markdown

    except Exception as exc:
        logger.warning("Docling extraction failed (%s). Falling back to pypdf plain text.", exc)
        page_texts = extract_page_texts(path)
        fallback = "\n\n".join(
            f"## Página {i + 1}\n\n{text.strip()}"
            for i, text in enumerate(page_texts)
            if text.strip()
        )
        logger.info("Fallback plain-text extraction: %d chars", len(fallback))
        return fallback
