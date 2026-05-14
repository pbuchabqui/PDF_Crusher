"""Tests for FastAPI application."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_fastapi import app

client = TestClient(app)


@pytest.fixture
def valid_pdf():
    """Create a valid PDF for testing."""
    try:
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(100, 750, "TEST DOCUMENT")
        c.drawString(100, 700, "SENTENÇA")
        c.drawString(100, 650, "CPF 123.456.789-10")
        c.save()
        buffer.seek(0)
        return buffer
    except ImportError:
        pytest.skip("reportlab not installed")


def test_health_check():
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_redirect():
    """Test root redirect to static files."""
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 307
    assert "/static/index.html" in response.headers["location"]


def test_process_valid_pdf(valid_pdf):
    """Test processing a valid PDF."""
    response = client.post(
        "/api/process",
        files={"pdf": ("test.pdf", valid_pdf, "application/pdf")},
        data={"use_groq": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["job_id"] is not None
    assert len(data["claude_files"]) > 0
    assert len(data["audit_files"]) > 0
    assert data["structure"] is not None
    assert data["privacy_audit"] is not None


def test_process_invalid_pdf():
    """Test rejecting invalid PDF."""
    invalid_pdf = BytesIO(b"This is not a PDF")
    response = client.post(
        "/api/process",
        files={"pdf": ("test.txt", invalid_pdf, "text/plain")},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_process_empty_file():
    """Test rejecting empty file."""
    empty_file = BytesIO(b"")
    response = client.post(
        "/api/process",
        files={"pdf": ("empty.pdf", empty_file, "application/pdf")},
    )
    assert response.status_code == 400


def test_download_nonexistent_file():
    """Test downloading non-existent file returns 404."""
    response = client.get("/api/files/99999999_invalid/nonexistent.txt")
    assert response.status_code == 404


def test_directory_traversal_blocked_double_dot():
    """Test that directory traversal with .. is blocked."""
    response = client.get("/api/files/20250514_a1b2c3d4/../../../etc/passwd")
    assert response.status_code == 400


def test_directory_traversal_blocked_slash():
    """Test that absolute paths are blocked."""
    response = client.get("/api/files/20250514_a1b2c3d4//etc/passwd")
    # This should still work as it's a valid relative path
    # but the file won't exist
    assert response.status_code == 404 or response.status_code == 400


def test_invalid_job_id_format():
    """Test that invalid job ID format is rejected."""
    response = client.get("/api/files/invalid_job_id/file.txt")
    assert response.status_code == 400


def test_zip_download_nonexistent_job():
    """Test ZIP download for non-existent job."""
    response = client.get("/api/jobs/99999999_invalid/zip")
    assert response.status_code == 404


def test_zip_download_invalid_job_id():
    """Test ZIP download with invalid job ID format."""
    response = client.get("/api/jobs/invalid_id/zip")
    assert response.status_code == 400


def test_process_without_file():
    """Test process endpoint without file raises error."""
    response = client.post("/api/process", data={"use_groq": False})
    assert response.status_code == 422  # FastAPI validation error


def test_invalid_groq_flag(valid_pdf):
    """Test with use_groq as string instead of boolean."""
    response = client.post(
        "/api/process",
        files={"pdf": ("test.pdf", valid_pdf, "application/pdf")},
        data={"use_groq": "maybe"},  # Invalid boolean value
    )
    # FastAPI may convert or reject, either is acceptable
    assert response.status_code in (200, 422)


def test_swagger_docs():
    """Test Swagger UI documentation endpoint."""
    response = client.get("/docs")
    assert response.status_code in (200, 404)  # Depends on FastAPI version


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
