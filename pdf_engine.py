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


def detect_scanned_pages(result_document: Any, text_threshold: int = 100, max_pages: int = 100) -> list[int]:
    """Detect pages that likely need OCR (have very little extracted text).

    Args:
        result_document: DoclingDocument from first pass (no OCR)
        text_threshold: Minimum characters to consider page "ok"
        max_pages: Maximum pages to process with OCR

    Returns:
        List of page indices that need OCR
    """
    scanned = []
    try:
        for page_num, page in enumerate(result_document.pages):
            text_length = len(page.export_to_text().strip())
            if text_length < text_threshold:
                scanned.append(page_num)
                if len(scanned) >= max_pages:
                    break
        logger.info(f"Detected {len(scanned)} pages needing OCR (threshold: {text_threshold} chars)")
    except Exception as e:
        logger.warning(f"Error detecting scanned pages: {e}")
    return scanned


def _merge_documents_hybrid(result_fast: Any, result_ocr: Any, scanned_page_indices: list[int]) -> Any:
    """Merge fast extraction with selective OCR results.

    Uses OCR results only for identified scanned pages, keeping original extraction for others.

    Args:
        result_fast: Conversion result without OCR
        result_ocr: Conversion result with OCR (may be full document)
        scanned_page_indices: List of page numbers that were OCR'd

    Returns:
        Merged DoclingDocument with best content for each page
    """
    if not scanned_page_indices:
        return result_fast.document

    try:
        merged_pages = []
        scanned_set = set(scanned_page_indices)

        for page_num, page_fast in enumerate(result_fast.document.pages):
            if page_num in scanned_set and hasattr(result_ocr, "document"):
                try:
                    if page_num < len(result_ocr.document.pages):
                        page_ocr = result_ocr.document.pages[page_num]
                        if len(page_ocr.export_to_text().strip()) > len(page_fast.export_to_text().strip()):
                            merged_pages.append(page_ocr)
                        else:
                            merged_pages.append(page_fast)
                    else:
                        merged_pages.append(page_fast)
                except Exception:
                    merged_pages.append(page_fast)
            else:
                merged_pages.append(page_fast)

        result_fast.document.pages = merged_pages
        return result_fast.document

    except Exception as e:
        logger.warning(f"Error merging documents, returning fast version: {e}")
        return result_fast.document


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


def extract_markdown_hybrid_ocr(pdf_path: str | Path, text_threshold: int = 100) -> str:
    """Extract with Hybrid OCR: fast pass + selective OCR on scanned pages.

    Two-pass approach:
    1. Fast extraction without OCR
    2. Detect pages with little text (likely scanned)
    3. OCR only those pages
    4. Merge results

    For 3000 pages: expects 7-15 minutes total (vs 60+ with full OCR)

    Args:
        pdf_path: Path to PDF file
        text_threshold: Minimum characters per page to skip OCR

    Returns:
        Markdown string with extracted content
    """
    path = Path(pdf_path)
    _validate_pdf(path)

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        total_start = time.time()

        logger.info("=== Hybrid OCR Extraction Started ===")

        # PASS 1: Fast extraction without OCR
        logger.info("Pass 1: Fast extraction (no OCR)...")
        pass1_start = time.time()

        options_fast = PdfPipelineOptions()
        options_fast.do_ocr = False
        options_fast.do_table_structure = False

        converter_fast = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options_fast)}
        )
        result_fast = converter_fast.convert(str(path))
        elapsed_pass1 = time.time() - pass1_start
        logger.info(f"Pass 1 complete in {elapsed_pass1:.1f}s")

        # DETECTION: Which pages need OCR?
        scanned_pages = detect_scanned_pages(result_fast.document, text_threshold=text_threshold)

        # If no pages need OCR, return fast result
        if not scanned_pages:
            markdown = result_fast.document.export_to_markdown()
            total_elapsed = time.time() - total_start
            logger.info(f"No OCR needed. Hybrid extraction complete in {total_elapsed:.1f}s. "
                       f"Content: {len(markdown)} chars")
            return markdown

        # PASS 2: Selective OCR on scanned pages
        logger.info(f"Pass 2: OCR on {len(scanned_pages)} pages...")
        pass2_start = time.time()

        options_ocr = PdfPipelineOptions()
        options_ocr.do_ocr = True
        options_ocr.do_table_structure = False

        converter_ocr = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options_ocr)}
        )
        result_ocr = converter_ocr.convert(str(path))
        elapsed_pass2 = time.time() - pass2_start
        logger.info(f"Pass 2 complete in {elapsed_pass2:.1f}s")

        # MERGE: Combine results
        logger.info("Merging extraction results...")
        merged_doc = _merge_documents_hybrid(result_fast, result_ocr, scanned_pages)

        markdown = merged_doc.export_to_markdown()
        total_elapsed = time.time() - total_start

        logger.info(f"=== Hybrid extraction complete ===")
        logger.info(f"Total time: {total_elapsed:.1f}s "
                   f"(Pass1: {elapsed_pass1:.1f}s, Pass2: {elapsed_pass2:.1f}s, "
                   f"OCR pages: {len(scanned_pages)})")
        logger.info(f"Extracted: {len(markdown)} chars")

        return markdown

    except Exception as exc:
        logger.warning(f"Hybrid OCR extraction failed ({exc}). Falling back to standard Docling...")
        return extract_markdown_docling(path)
