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


def detect_scanned_pages(result_document: Any, text_threshold: int = 100, max_pages_to_check: int = 50) -> list[int]:
    """Detect pages that likely need OCR (have very little extracted text).

    Optimized: only samples pages to save time on large documents.

    Args:
        result_document: DoclingDocument from first pass (no OCR)
        text_threshold: Minimum characters to consider page "ok"
        max_pages_to_check: Maximum pages to analyze (samples for large docs)

    Returns:
        List of page indices that need OCR
    """
    scanned = []
    try:
        pages = result_document.pages
        total_pages = len(pages)

        # For large documents, sample every Nth page instead of checking all
        if total_pages > 100:
            step = max(1, total_pages // 50)  # Sample ~50 pages max
            logger.info(f"Large document ({total_pages} pages): sampling every {step}th page")
        else:
            step = 1

        for page_num in range(0, min(total_pages, max_pages_to_check), step):
            try:
                page = pages[page_num]
                text_length = len(page.export_to_text().strip())
                if text_length < text_threshold:
                    scanned.append(page_num)
            except Exception as e:
                logger.debug(f"Error checking page {page_num}: {e}")

        logger.info(f"Detected {len(scanned)} pages needing OCR (threshold: {text_threshold} chars, sampled {total_pages//step if step > 1 else total_pages} pages)")

    except Exception as e:
        logger.warning(f"Error detecting scanned pages: {e}")

    return scanned


def _merge_documents_hybrid(result_fast: Any, result_ocr: Any, scanned_page_indices: list[int]) -> Any:
    """Merge fast extraction with selective OCR results (simplified).

    Strategy: If there are very few scanned pages, just use OCR result (faster).
    Otherwise, use fast result (OCR didn't help much anyway).

    Args:
        result_fast: Conversion result without OCR
        result_ocr: Conversion result with OCR
        scanned_page_indices: List of page numbers that were identified as scanned

    Returns:
        Best DoclingDocument
    """
    if not scanned_page_indices:
        return result_fast.document

    # If few scanned pages detected, OCR pass should have gotten them all
    # Just return the full OCR result
    if len(scanned_page_indices) <= 10:
        try:
            return result_ocr.document
        except Exception:
            return result_fast.document

    # If many pages detected as scanned, merge is expensive
    # Use fast result since it already has most content
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

    Optimized two-pass approach for large documents:
    1. Fast extraction without OCR
    2. Sample pages to detect scanned content
    3. Skip OCR pass if:
       - No scanned pages detected
       - Too many pages need OCR (document is mostly scanned)
    4. Otherwise, do selective OCR

    For 3000 pages: expects 5-15 minutes total

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
        total_pages = len(result_fast.document.pages)
        logger.info(f"Pass 1 complete in {elapsed_pass1:.1f}s ({total_pages} pages)")

        # DETECTION: Which pages need OCR? (sampled for large docs)
        scanned_pages = detect_scanned_pages(result_fast.document, text_threshold=text_threshold)

        # If no pages need OCR, return fast result immediately
        if not scanned_pages:
            markdown = result_fast.document.export_to_markdown()
            total_elapsed = time.time() - total_start
            logger.info(f"No OCR needed. Complete in {total_elapsed:.1f}s. Content: {len(markdown)} chars")
            return markdown

        # If too many pages need OCR (>30% of document), skip OCR pass
        # Document is mostly scanned, fast pass is good enough
        estimated_total_scanned = len(scanned_pages) * (total_pages // max(1, total_pages // 50))
        if estimated_total_scanned > total_pages * 0.3:
            logger.info(f"Estimated {estimated_total_scanned} scanned pages (>30%). Skipping OCR pass.")
            markdown = result_fast.document.export_to_markdown()
            total_elapsed = time.time() - total_start
            logger.info(f"Complete in {total_elapsed:.1f}s. Content: {len(markdown)} chars")
            return markdown

        # PASS 2: Selective OCR on detected scanned pages
        logger.info(f"Pass 2: OCR on {len(scanned_pages)} sampled pages...")
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

        # MERGE: Combine results (simplified)
        merged_doc = _merge_documents_hybrid(result_fast, result_ocr, scanned_pages)

        markdown = merged_doc.export_to_markdown()
        total_elapsed = time.time() - total_start

        logger.info(f"=== Hybrid extraction complete in {total_elapsed:.1f}s ===")
        logger.info(f"Pass1: {elapsed_pass1:.1f}s, Pass2: {elapsed_pass2:.1f}s, Content: {len(markdown)} chars")

        return markdown

    except Exception as exc:
        logger.warning(f"Hybrid OCR extraction failed ({exc}). Falling back to standard Docling...")
        return extract_markdown_docling(path)
