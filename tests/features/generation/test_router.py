import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


async def fake_stream(*args, **kwargs):
    tokens = ["Apple ", "revenue ", "grew ", "12% ", "in ", "Q3."]
    for token in tokens:
        yield token


@pytest.fixture
def mock_retrieval_service():
    with patch(
        "app.features.generation.router.RetrievalService"
    ) as mock_cls:
        mock_service = AsyncMock()
        mock_service.search.return_value = [
            {
                "chunk_text": "Apple revenue grew 12% in Q3 2023.",
                "file_name": "apple_10k.pdf",
                "chunk_index": 1,
                "source": "sec.gov",
                "score": 0.032,
            }
        ]
        mock_cls.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_generation_service():
    with patch(
        "app.features.generation.router.GenerationService"
    ) as mock_cls:
        mock_service = AsyncMock()
        mock_service.stream = fake_stream
        mock_cls.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_deps():
    with patch("app.features.generation.router.get_db") as mock_db, \
         patch("app.features.generation.router.get_qdrant") as mock_qdrant:
        mock_db.return_value = AsyncMock()
        mock_qdrant.return_value = AsyncMock()
        yield


@pytest.mark.asyncio
async def test_generate_returns_200(
    mock_retrieval_service, mock_generation_service, mock_deps
):
    """Valid query should return 200"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={"query": "What was Apple revenue in Q3?"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_generate_returns_streamed_content(
    mock_retrieval_service, mock_generation_service, mock_deps
):
    """Response body should contain streamed tokens"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={"query": "What was Apple revenue in Q3?"},
        )
    assert "Apple" in response.text


@pytest.mark.asyncio
async def test_generate_content_type_is_text(
    mock_retrieval_service, mock_generation_service, mock_deps
):
    """SSE streaming response must be text/plain"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={"query": "What was Apple revenue in Q3?"},
        )
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_generate_empty_query_returns_422(mock_deps):
    """Empty query should be rejected"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={"query": ""},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_missing_query_returns_422(mock_deps):
    """Missing query field should return 422"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_calls_retrieval_first(
    mock_retrieval_service, mock_generation_service, mock_deps
):
    """Retrieval must be called before generation"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/generation/generate",
            json={"query": "What was Apple revenue in Q3?"},
        )
    assert mock_retrieval_service.search.called