import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


async def fake_progress(*args, **kwargs):
    yield {"status": "extracting", "message": "Extracting..."}
    yield {"status": "embedding", "message": "Embedding 2 chunks...", "total": 2}
    yield {"status": "done", "file_name": "apple_10k.pdf", "chunks_ingested": 42, "source": "https://sec.gov/apple"}


@pytest.fixture
def mock_ingest_service():
    with patch(
        "app.features.ingestion.router.IngestionService"
    ) as mock_cls:
        mock_service = AsyncMock()
        mock_service.ingest_with_progress = fake_progress
        mock_cls.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_deps():
    with patch("app.features.ingestion.router.get_db") as mock_db, \
         patch("app.features.ingestion.router.get_qdrant") as mock_qdrant:
        mock_db.return_value = AsyncMock()
        mock_qdrant.return_value = AsyncMock()
        yield


@pytest.mark.asyncio
async def test_upload_pdf_returns_200(mock_ingest_service, mock_deps):
    """Valid PDF upload should return 200 with ingestion summary"""
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
async def test_upload_streams_progress_events(mock_ingest_service, mock_deps):
    """Response should contain SSE progress events"""
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
async def test_upload_streams_done_event(mock_ingest_service, mock_deps):
    """Final SSE event must contain done status with chunk count"""
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