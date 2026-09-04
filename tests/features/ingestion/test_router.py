import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.features.auth.models import User


async def fake_progress(*args, **kwargs):
    yield {"status": "extracting", "message": "Extracting..."}
    yield {"status": "embedding", "message": "Embedding 2 chunks...", "total": 2}
    yield {
        "status": "done",
        "file_name": "apple_10k.pdf",
        "chunks_ingested": 42,
        "source": "https://sec.gov/apple",
    }


def setup_upload_mocks(mock_doc_svc, mock_ing_svc, mock_session_local, file_exists=False):
    """Helper to setup all mocks needed for upload endpoint"""
    mock_doc = AsyncMock()
    mock_doc.file_exists.return_value = file_exists
    mock_doc_svc.return_value = mock_doc

    mock_ing = AsyncMock()
    mock_ing.ingest_with_progress = fake_progress
    mock_ing_svc.return_value = mock_ing

    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_doc, mock_ing


@pytest.fixture
def mock_deps():
    with patch("app.features.ingestion.router.get_db") as mock_db, \
         patch("app.features.ingestion.router.get_qdrant") as mock_qdrant:
        mock_db.return_value = AsyncMock()
        mock_qdrant.return_value = AsyncMock()
        yield


@pytest.mark.asyncio
async def test_upload_pdf_returns_200(mock_deps):
    """Valid PDF upload should return 200"""
    with patch("app.features.ingestion.router.DocumentService") as mock_doc_svc, \
         patch("app.features.ingestion.router.IngestionService") as mock_ing_svc, \
         patch("app.features.ingestion.router.AsyncSessionLocal") as mock_session_local:

        setup_upload_mocks(mock_doc_svc, mock_ing_svc, mock_session_local)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/ingestion/upload",
                files={"file": ("apple_10k.pdf", b"%PDF-1.4 mock", "application/pdf")},
                data={"source": "https://sec.gov/apple"},
            )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_non_pdf_returns_400(mock_deps):
    """Non-PDF files should be rejected with 400"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/ingestion/upload",
            files={"file": ("report.txt", b"plain text", "text/plain")},
            data={"source": "local"},
        )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_missing_file_returns_422(mock_deps):
    """Missing file should return 422 unprocessable entity"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/ingestion/upload",
            data={"source": "local"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_streams_progress_events(mock_deps):
    """Response should contain SSE progress events"""
    with patch("app.features.ingestion.router.DocumentService") as mock_doc_svc, \
         patch("app.features.ingestion.router.IngestionService") as mock_ing_svc, \
         patch("app.features.ingestion.router.AsyncSessionLocal") as mock_session_local:

        setup_upload_mocks(mock_doc_svc, mock_ing_svc, mock_session_local)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/ingestion/upload",
                files={"file": ("apple_10k.pdf", b"%PDF-1.4 mock", "application/pdf")},
                data={"source": "https://sec.gov/apple"},
            )
    assert "extracting" in response.text
    assert "done" in response.text


@pytest.mark.asyncio
async def test_upload_streams_done_event(mock_deps):
    """Final SSE event must contain done status with chunk count"""
    with patch("app.features.ingestion.router.DocumentService") as mock_doc_svc, \
         patch("app.features.ingestion.router.IngestionService") as mock_ing_svc, \
         patch("app.features.ingestion.router.AsyncSessionLocal") as mock_session_local:

        setup_upload_mocks(mock_doc_svc, mock_ing_svc, mock_session_local)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/ingestion/upload",
                files={"file": ("apple_10k.pdf", b"%PDF-1.4 mock", "application/pdf")},
                data={"source": "https://sec.gov/apple"},
            )
    assert "chunks_ingested" in response.text
    assert "apple_10k.pdf" in response.text


@pytest.mark.asyncio
async def test_duplicate_ingestion_guard(mock_deps):
    """Re-ingesting same file should return 409 conflict"""
    with patch("app.features.ingestion.router.DocumentService") as mock_doc_svc, \
         patch("app.features.ingestion.router.IngestionService") as mock_ing_svc, \
         patch("app.features.ingestion.router.AsyncSessionLocal") as mock_session_local:

        setup_upload_mocks(
            mock_doc_svc, mock_ing_svc, mock_session_local,
            file_exists=True,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/ingestion/upload",
                files={"file": ("apple_10k.pdf", b"%PDF-1.4 mock", "application/pdf")},
                data={"source": "https://sec.gov/apple"},
            )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_documents_returns_200(mock_deps):
    """List endpoint should return 200"""
    with patch("app.features.ingestion.router.DocumentService") as mock_doc_svc:
        mock_doc = AsyncMock()
        mock_doc.list_documents.return_value = [
            {
                "file_name": "apple_10k.pdf",
                "source": "sec.gov",
                "chunk_count": 42,
                "created_at": "2024-01-15T10:00:00",
            }
        ]
        mock_doc_svc.return_value = mock_doc

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/ingestion/documents")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_documents_returns_correct_schema(mock_deps):
    """Response must contain documents list and total"""
    with patch("app.features.ingestion.router.DocumentService") as mock_doc_svc:
        mock_doc = AsyncMock()
        mock_doc.list_documents.return_value = [
            {
                "file_name": "apple_10k.pdf",
                "source": "sec.gov",
                "chunk_count": 42,
                "created_at": "2024-01-15T10:00:00",
            }
        ]
        mock_doc_svc.return_value = mock_doc

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/ingestion/documents")
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_delete_document_returns_200(mock_deps):
    """Delete endpoint should return 200"""
    with patch("app.features.ingestion.router.DocumentService") as mock_doc_svc:
        mock_doc = AsyncMock()
        mock_doc.delete_document.return_value = {
            "file_name": "apple_10k.pdf",
            "chunks_deleted": 42,
        }
        mock_doc_svc.return_value = mock_doc

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.delete(
                "/api/v1/ingestion/documents/apple_10k.pdf"
            )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_document_returns_chunk_count(mock_deps):
    """Delete response must include how many chunks were removed"""
    with patch("app.features.ingestion.router.DocumentService") as mock_doc_svc:
        mock_doc = AsyncMock()
        mock_doc.delete_document.return_value = {
            "file_name": "apple_10k.pdf",
            "chunks_deleted": 42,
        }
        mock_doc_svc.return_value = mock_doc

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.delete(
                "/api/v1/ingestion/documents/apple_10k.pdf"
            )
    data = response.json()
    assert "chunks_deleted" in data
    assert data["chunks_deleted"] == 42
    assert "file_name" in data


@pytest.mark.asyncio
async def test_delete_nonexistent_document_returns_404(mock_deps):
    """Deleting a file that doesn't exist should return 404"""
    with patch("app.features.ingestion.router.DocumentService") as mock_doc_svc:
        mock_doc = AsyncMock()
        mock_doc.delete_document.return_value = {
            "file_name": "nonexistent.pdf",
            "chunks_deleted": 0,
        }
        mock_doc_svc.return_value = mock_doc

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.delete(
                "/api/v1/ingestion/documents/nonexistent.pdf"
            )
    assert response.status_code == 404


# ---- Sharing endpoints ----


@pytest.fixture
def mock_doc_svc():
    with patch("app.features.ingestion.router.DocumentService") as mock_cls:
        mock_svc = AsyncMock()
        mock_cls.return_value = mock_svc
        yield mock_svc


def mock_target_user(user_id=2):
    return User(
        id=user_id, email="bob@example.com", username="bob",
        hashed_password="x", is_active=True,
    )


@pytest.mark.asyncio
async def test_share_document_returns_200(mock_deps, mock_doc_svc):
    """Owner sharing a file with another user by email returns 200"""
    mock_doc_svc.is_owner.return_value = True
    mock_doc_svc.share_file.return_value = True
    with patch(
        "app.features.ingestion.router.get_user_by_email",
        new_callable=AsyncMock,
        return_value=mock_target_user(),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/ingestion/shares", json={
                "file_name": "apple_10k.pdf",
                "user_email": "bob@example.com",
            })
    assert response.status_code == 200
    assert response.json()["shared_with"] == 2


@pytest.mark.asyncio
async def test_share_document_target_not_found_returns_404(mock_deps, mock_doc_svc):
    """Sharing with a non-existent email returns 404"""
    with patch(
        "app.features.ingestion.router.get_user_by_email",
        new_callable=AsyncMock,
        return_value=None,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/ingestion/shares", json={
                "file_name": "apple_10k.pdf",
                "user_email": "ghost@example.com",
            })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_share_document_non_owner_returns_403(mock_deps, mock_doc_svc):
    """Non-owner (and non-admin) cannot share a file they don't own"""
    mock_doc_svc.is_owner.return_value = False
    with patch(
        "app.features.ingestion.router.get_user_by_email",
        new_callable=AsyncMock,
        return_value=mock_target_user(),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/ingestion/shares", json={
                "file_name": "apple_10k.pdf",
                "user_email": "bob@example.com",
            })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_share_document_file_not_found_returns_404(mock_deps, mock_doc_svc):
    """Sharing a file the owner doesn't actually have returns 404"""
    mock_doc_svc.is_owner.return_value = True
    mock_doc_svc.share_file.return_value = False
    with patch(
        "app.features.ingestion.router.get_user_by_email",
        new_callable=AsyncMock,
        return_value=mock_target_user(),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/ingestion/shares", json={
                "file_name": "missing.pdf",
                "user_email": "bob@example.com",
            })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unshare_document_returns_200(mock_deps, mock_doc_svc):
    """Owner revoking a share returns 200 with removed count"""
    mock_doc_svc.is_owner.return_value = True
    mock_doc_svc.unshare_file.return_value = 1
    with patch(
        "app.features.ingestion.router.get_user_by_email",
        new_callable=AsyncMock,
        return_value=mock_target_user(),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.request("DELETE", "/api/v1/ingestion/shares", json={
                "file_name": "apple_10k.pdf",
                "user_email": "bob@example.com",
            })
    assert response.status_code == 200
    assert response.json()["removed"] == 1


@pytest.mark.asyncio
async def test_unshare_non_owner_returns_403(mock_deps, mock_doc_svc):
    """Non-owner cannot unshare a file they don't own"""
    mock_doc_svc.is_owner.return_value = False
    with patch(
        "app.features.ingestion.router.get_user_by_email",
        new_callable=AsyncMock,
        return_value=mock_target_user(),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.request("DELETE", "/api/v1/ingestion/shares", json={
                "file_name": "apple_10k.pdf",
                "user_email": "bob@example.com",
            })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_document_shares_returns_200(mock_deps, mock_doc_svc):
    """Owner listing shares returns 200 with share list"""
    mock_doc_svc.is_owner.return_value = True
    mock_doc_svc.list_shares.return_value = [
        {"granted_to_user_id": 2, "created_at": "2024-01-15T10:00:00"},
    ]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/ingestion/shares/apple_10k.pdf")
    assert response.status_code == 200
    assert response.json()["shares"][0]["granted_to_user_id"] == 2


@pytest.mark.asyncio
async def test_list_document_shares_non_owner_returns_403(mock_deps, mock_doc_svc):
    """Non-owner viewing shares returns 403"""
    mock_doc_svc.is_owner.return_value = False
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/ingestion/shares/apple_10k.pdf")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_share_document_missing_fields_returns_422(mock_deps, mock_doc_svc):
    """Share request missing user_email returns 422"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/ingestion/shares", json={
            "file_name": "apple_10k.pdf",
        })
    assert response.status_code == 422