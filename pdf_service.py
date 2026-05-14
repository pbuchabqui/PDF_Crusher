"""Service layer for PDF processing with file management."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from config import PipelineConfig
from pipeline import run_pipeline

logger = logging.getLogger(__name__)


class ProcessRequest(BaseModel):
    use_groq: bool = False
    groq_api_key: str | None = None


class ProcessResponse(BaseModel):
    status: str
    job_id: str | None = None
    output_dir: str | None = None
    claude_files: list[str] = []
    audit_files: list[str] = []
    structure: dict | None = None
    privacy_audit: dict | None = None
    error: str | None = None
    error_type: str | None = None
    timestamp: str = ""


def create_job_dir(base_dir: str = "./pdf_outputs") -> tuple[str, Path]:
    """Create unique job directory with timestamp and random ID."""
    job_id = datetime.now().strftime("%Y%m%d") + "_" + str(uuid.uuid4())[:8]
    job_dir = Path(base_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created job directory: {job_dir}")
    return job_id, job_dir


def validate_pdf(pdf_bytes: bytes) -> str | None:
    """Validate PDF magic bytes and size."""
    if not pdf_bytes.startswith(b"%PDF-"):
        return "Invalid PDF file (magic bytes check failed)"
    if len(pdf_bytes) < 1024:
        return "PDF file too small (corrupted or incomplete)"
    return None


async def process_pdf(
    pdf_bytes: bytes,
    request: ProcessRequest,
) -> ProcessResponse:
    """Process PDF with complete error handling and file management."""
    job_id = None
    job_dir = None

    try:
        # Create job directory
        job_id, job_dir = create_job_dir()
        pdf_path = job_dir / "upload.pdf"
        output_dir = job_dir / "outputs"

        # Validate PDF
        validation_error = validate_pdf(pdf_bytes)
        if validation_error:
            logger.warning(f"PDF validation failed for job {job_id}: {validation_error}")
            return ProcessResponse(
                status="error",
                job_id=job_id,
                error=validation_error,
                error_type="validation",
                timestamp=datetime.now().isoformat(),
            )

        # Write PDF to disk
        pdf_path.write_bytes(pdf_bytes)
        logger.info(f"PDF written to {pdf_path} for job {job_id}")

        # Prepare config
        config = PipelineConfig(
            use_groq=request.use_groq,
            groq_api_key=request.groq_api_key or os.getenv("GROQ_API_KEY"),
        )

        # Validate config
        try:
            config.validate()
        except ValueError as e:
            logger.warning(f"Config validation error in job {job_id}: {e}")
            return ProcessResponse(
                status="error",
                job_id=job_id,
                error=str(e),
                error_type="validation",
                timestamp=datetime.now().isoformat(),
            )

        # Run pipeline
        logger.info(f"Starting pipeline for job {job_id}")
        result = run_pipeline(pdf_path, output_dir, config=config)
        logger.info(f"Pipeline completed successfully for job {job_id}")

        return ProcessResponse(
            status="success",
            job_id=job_id,
            output_dir=str(output_dir),
            claude_files=result["claude_files"],
            audit_files=result["audit_files"],
            structure=result["structure"],
            privacy_audit=result["privacy_audit"],
            timestamp=datetime.now().isoformat(),
        )

    except ValueError as e:
        logger.warning(f"Validation error in job {job_id}: {e}")
        return ProcessResponse(
            status="error",
            job_id=job_id,
            error=str(e),
            error_type="validation",
            timestamp=datetime.now().isoformat(),
        )

    except RuntimeError as e:
        error_type = "groq" if "Groq" in str(e) else "processing"
        logger.error(f"Runtime error in job {job_id}: {e}")
        return ProcessResponse(
            status="error",
            job_id=job_id,
            error=str(e),
            error_type=error_type,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.exception(f"Unexpected error in job {job_id}: {e}")
        return ProcessResponse(
            status="error",
            job_id=job_id,
            error=str(e),
            error_type="unexpected",
            timestamp=datetime.now().isoformat(),
        )
