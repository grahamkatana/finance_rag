import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
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
def mock_audit():
    with patch(
        "app.features.generation.router.process_query_audit"
    ) as mock_task:
        mock_task.delay = MagicMock()
        yield mock_task


@pytest.fixture
def mock_deps():
    with patch("app.features.generation.router.get_db") as mock_db, \
         patch("app.features.generation.router.get_qdrant") as mock_qdrant:
        mock_db.return_value = AsyncMock()
        mock_qdrant.return_value = AsyncMock()
        yield


@pytest.mark.asyncio
async def test_generate_returns_200(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """Valid query should return 200"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={
                "query": "What was Apple revenue in Q3?",
                "client_id": "test-user",
            },
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_generate_returns_streamed_content(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """Response body should contain streamed tokens"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={
                "query": "What was Apple revenue in Q3?",
                "client_id": "test-user",
            },
        )
    assert "Apple" in response.text


@pytest.mark.asyncio
async def test_generate_content_type_is_text(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """SSE streaming response must be text/plain"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={
                "query": "What was Apple revenue in Q3?",
                "client_id": "test-user",
            },
        )
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_generate_empty_query_returns_422(mock_audit, mock_deps):
    """Empty query should be rejected"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={
                "query": "",
                "client_id": "test-user",
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_missing_query_returns_422(mock_audit, mock_deps):
    """Missing query field should return 422"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/generate",
            json={"client_id": "test-user"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_calls_retrieval_first(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """Retrieval must be called before generation"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/generation/generate",
            json={
                "query": "What was Apple revenue in Q3?",
                "client_id": "test-user",
            },
        )
    assert mock_retrieval_service.search.called


@pytest.mark.asyncio
async def test_generate_fires_audit_task(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """Audit task must be fired after generation completes"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/generation/generate",
            json={
                "query": "What was Apple revenue in Q3?",
                "client_id": "test-user",
            },
        )
    assert mock_audit.delay.called


@pytest.mark.asyncio
async def test_generate_audit_receives_client_id(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """Audit task must receive the client_id"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/generation/generate",
            json={
                "query": "What was Apple revenue in Q3?",
                "client_id": "graham-test",
            },
        )
    call_kwargs = mock_audit.delay.call_args.kwargs
    assert call_kwargs["client_id"] == "graham-test"


@pytest.mark.asyncio
async def test_generate_default_client_id(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """client_id should default to anonymous if not provided"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/generation/generate",
            json={"query": "What was Apple revenue in Q3?"},
        )
    call_kwargs = mock_audit.delay.call_args.kwargs
    assert call_kwargs["client_id"] == "anonymous"