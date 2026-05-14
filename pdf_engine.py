"""PDF extraction helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def pdf_info(pdf_path: str | Path) -> dict[str, Any]:
    from pypdf import PdfReader

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
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def extract_markdown_pypdf(pdf_path: str | Path) -> str:
    parts = []
    for index, text in enumerate(extract_page_texts(pdf_path), start=1):
        content = text.strip() or "[Página sem texto extraível por pypdf.]"
        parts.append(f"## Página PDF {index:04d}\n\n{content}")
    return "\n\n".join(parts)


def extract_markdown_docling(pdf_path: str | Path) -> str:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ModuleNotFoundError as exc:
        raise RuntimeError("Docling não está instalado. Instale com `pip install docling` para usar PDF_CRUSHER_EXTRACTOR=docling.") from exc

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


def extract_markdown(pdf_path: str | Path, mode: str | None = None) -> str:
    extractor = (mode or os.getenv("PDF_CRUSHER_EXTRACTOR", "pypdf")).strip().lower()
    if extractor == "docling":
        return extract_markdown_docling(pdf_path)
    if extractor == "auto":
        try:
            return extract_markdown_docling(pdf_path)
        except Exception:
            return extract_markdown_pypdf(pdf_path)
    if extractor != "pypdf":
        raise ValueError("PDF_CRUSHER_EXTRACTOR deve ser 'pypdf', 'docling' ou 'auto'.")
    return extract_markdown_pypdf(pdf_path)
