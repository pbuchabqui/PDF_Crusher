"""FastAPI application for PDF_Crusher."""

from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pdf_service import ProcessResponse, ProcessRequest, process_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF_Crusher API",
    description="Processa PDFs jurídicos com higienização de dados pessoais",
    version="1.0.0",
)

# Serve static files (HTML, CSS, JS)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("Static files mounted from ./static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")


@app.post("/api/process")
async def process_pdf_endpoint(
    pdf: UploadFile = File(...),
    use_groq: bool = False,
    groq_api_key: str | None = None,
) -> ProcessResponse:
    """
    Upload PDF e processa com higienização.

    - **pdf**: Arquivo PDF para processar
    - **use_groq**: Usar Groq para anonimizar nomes (true/false)
    - **groq_api_key**: Chave da API Groq (opcional, lê env se omitido)
    """
    logger.info(f"Processing PDF: {pdf.filename}")

    # Read PDF bytes
    pdf_bytes = await pdf.read()

    # Process via service
    request = ProcessRequest(
        use_groq=use_groq,
        groq_api_key=groq_api_key,
    )
    response = await process_pdf(pdf_bytes, request)

    # Return appropriate HTTP status
    if response.status == "error":
        status_code = 400 if response.error_type == "validation" else 500
        logger.warning(f"Process error ({response.error_type}): {response.error}")
        raise HTTPException(status_code=status_code, detail=response.error)

    logger.info(f"Successfully processed PDF: job_id={response.job_id}")
    return response


@app.get("/api/files/{job_id}/{filepath:path}")
async def download_file(job_id: str, filepath: str):
    """
    Download arquivo processado.

    Exemplo: /api/files/20250514_a1b2c3d4/claude/PDF_CRUSHER_CONTEXT.md
    """
    # Validate job_id format
    if not _is_valid_job_id(job_id):
        logger.warning(f"Invalid job ID format: {job_id}")
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    # Prevent directory traversal
    if ".." in filepath or filepath.startswith("/"):
        logger.warning(f"Directory traversal attempt: {filepath}")
        raise HTTPException(status_code=400, detail="Invalid file path")

    file_path = Path("./pdf_outputs") / job_id / filepath

    # Check existence
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")

    # Check that file is within job directory
    try:
        file_path.resolve().relative_to((Path("./pdf_outputs") / job_id).resolve())
    except ValueError:
        logger.warning(f"Access denied to file outside job directory: {file_path}")
        raise HTTPException(status_code=403, detail="Access denied")

    logger.info(f"Downloading file: {file_path}")
    return FileResponse(file_path)


@app.get("/api/jobs/{job_id}/zip")
async def download_job_zip(job_id: str):
    """Download todos os arquivos do job em ZIP."""
    if not _is_valid_job_id(job_id):
        logger.warning(f"Invalid job ID for ZIP: {job_id}")
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job_dir = Path("./pdf_outputs") / job_id
    if not job_dir.exists():
        logger.warning(f"Job directory not found: {job_dir}")
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(f"Creating ZIP archive for job: {job_id}")

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in job_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(job_dir)
                zf.write(file_path, arcname)

    zip_buffer.seek(0)
    logger.info(f"ZIP archive created, size: {len(zip_buffer.getvalue())} bytes")

    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={job_id}.zip"},
    )


@app.get("/")
async def root():
    """Redireciona para /static/index.html"""
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "pdf_crusher_api"}


@app.get("/docs")
async def swagger_ui():
    """Swagger UI documentation."""
    from fastapi.openapi.docs import get_swagger_ui_html

    return get_swagger_ui_html(openapi_url="/openapi.json", title="API")


def _is_valid_job_id(job_id: str) -> bool:
    """Validate job ID format (YYYYMMDD_12345678)."""
    return bool(re.match(r"^\d{8}_[a-f0-9]{8}$", job_id))


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    return {
        "error": exc.detail,
        "status_code": exc.status_code,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
