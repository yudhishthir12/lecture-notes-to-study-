"""Integration tests for LectureForge AI FastAPI API endpoints.

Tests verify:
- Document upload (valid file, unsupported extension, missing file)
- Document listing with pagination
- Single document retrieval (existing vs 404)
- Document deletion
- Document processing status endpoint
- Study pack generation trigger (rejection when GEMINI_API_KEY is not set)
"""

import io
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document, DocumentStatus, FileType


@pytest.mark.asyncio
async def test_upload_document_txt_success(client: httpx.AsyncClient):
    """Verify successful upload of a plain text lecture file returns 201 Created."""
    file_content = b"Lecture 1: Introduction to Operating Systems\nProcesses and Threads."
    files = {
        "file": ("os_lecture.txt", file_content, "text/plain"),
    }

    response = await client.post("/api/documents/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "os_lecture.txt"
    assert data["file_type"] == "txt"
    assert data["status"] == "uploaded"
    assert "id" in data


@pytest.mark.asyncio
async def test_upload_document_pdf_success(client: httpx.AsyncClient):
    """Verify successful upload of a PDF lecture file returns 201 Created."""
    # Minimal PDF bytes
    file_content = b"%PDF-1.4 sample pdf content for testing upload endpoint"
    files = {
        "file": ("lecture_slides.pdf", file_content, "application/pdf"),
    }

    response = await client.post("/api/documents/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "lecture_slides.pdf"
    assert data["file_type"] == "pdf"
    assert data["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_document_invalid_extension(client: httpx.AsyncClient):
    """Verify uploading an unsupported file format (e.g. .exe) returns 400 Bad Request."""
    files = {
        "file": ("malware.exe", b"binary content", "application/octet-stream"),
    }

    response = await client.post("/api/documents/upload", files=files)

    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file format" in data["detail"]


@pytest.mark.asyncio
async def test_upload_document_empty_filename(client: httpx.AsyncClient):
    """Verify uploading without a valid file returns 400 or 422 error."""
    response = await client.post("/api/documents/upload", data={})
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_list_documents_empty(client: httpx.AsyncClient):
    """Verify GET /api/documents on an empty database returns total 0."""
    response = await client.get("/api/documents")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1
    assert data["page_size"] == 10


@pytest.mark.asyncio
async def test_list_documents_with_records(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify GET /api/documents returns paginated list of created documents."""
    # Seed 2 documents into the test database
    doc1 = Document(
        id=uuid.uuid4(),
        filename="Doc1.pdf",
        file_type="pdf",
        file_path="/tmp/Doc1.pdf",
        file_size=1024,
        status=DocumentStatus.UPLOADED,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        filename="Doc2.txt",
        file_type="txt",
        file_path="/tmp/Doc2.txt",
        file_size=2048,
        status=DocumentStatus.COMPLETED,
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()

    response = await client.get("/api/documents?page=1&page_size=10")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_document_detail_success(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify GET /api/documents/{id} returns full document details."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="Algorithms.pdf",
        file_type="pdf",
        file_path="/tmp/Algorithms.pdf",
        file_size=50000,
        status=DocumentStatus.UPLOADED,
        extracted_text="Sample extracted text from lecture.",
    )
    db_session.add(doc)
    await db_session.commit()

    response = await client.get(f"/api/documents/{doc_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(doc_id)
    assert data["filename"] == "Algorithms.pdf"
    assert data["extracted_text"] == "Sample extracted text from lecture."


@pytest.mark.asyncio
async def test_get_document_not_found(client: httpx.AsyncClient):
    """Verify GET /api/documents/{id} returns 404 for non-existent UUID."""
    random_id = uuid.uuid4()
    response = await client.get(f"/api/documents/{random_id}")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


@pytest.mark.asyncio
async def test_get_document_status(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify GET /api/documents/{id}/status returns document progress."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="Database.pptx",
        file_type="pptx",
        file_path="/tmp/Database.pptx",
        file_size=34000,
        status=DocumentStatus.EXTRACTING_CONCEPTS,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await client.get(f"/api/documents/{doc_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(doc_id)
    assert data["status"] == "extracting_concepts"
    assert data["progress_percentage"] == 55


@pytest.mark.asyncio
async def test_delete_document_success(
    client: httpx.AsyncClient, db_session: AsyncSession, tmp_path: Path
):
    """Verify DELETE /api/documents/{id} removes the document and file, returning 204."""
    dummy_file = tmp_path / "to_delete.txt"
    dummy_file.write_text("temporary content", encoding="utf-8")

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="to_delete.txt",
        file_type="txt",
        file_path=str(dummy_file),
        file_size=100,
        status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await client.delete(f"/api/documents/{doc_id}")
    assert response.status_code == 204

    # Verify file is deleted from disk
    assert not dummy_file.exists()

    # Verify document is no longer in database
    get_res = await client.get(f"/api/documents/{doc_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_not_found(client: httpx.AsyncClient):
    """Verify DELETE /api/documents/{id} returns 404 for non-existent document."""
    random_id = uuid.uuid4()
    response = await client.delete(f"/api/documents/{random_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_endpoint_requires_gemini_api_key(
    client: httpx.AsyncClient, db_session: AsyncSession
):
    """Verify POST /api/documents/{id}/generate returns 400 when GEMINI_API_KEY is unset."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="Physics.pdf",
        file_type="pdf",
        file_path="/tmp/Physics.pdf",
        file_size=1000,
        status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()

    # Ensure GEMINI_API_KEY is empty
    original_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = None

    try:
        response = await client.post(f"/api/documents/{doc_id}/generate")
        assert response.status_code == 400
        data = response.json()
        assert "Gemini API key not configured" in data["detail"]
    finally:
        settings.GEMINI_API_KEY = original_key
