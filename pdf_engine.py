"""PDF extraction helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from pypdf import PdfReader


def pdf_info(pdf_path: str | Path) -> dict[str, Any]:
    path = Path(pdf_path)
    reader = PdfReader(str(path))
    return {
        "nome": path.name,
        "tamanho_bytes": path.stat().st_size,
        "paginas_totais": len(reader.pages),
        "criptografado": reader.is_encrypted,
        "metadados": dict(reader.metadata or {}),
    }


def extract_page_texts(pdf_path: str | Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def extract_markdown_docling(pdf_path: str | Path) -> str:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    result = converter.convert(str(pdf_path))
    return result.document.export_to_markdown()
