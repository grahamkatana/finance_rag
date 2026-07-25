import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


@pytest.fixture
def mock_search_results():
    return [
        {
            "chunk_text": "Apple revenue grew 12% in Q3 2023.",
            "file_name": "apple_10k.pdf",
            "chunk_index": 1,
            "source": "sec.gov",
            "score": 0.032,
        },
        {
            "chunk_text": "Net income rose to $19.9 billion.",
            "file_name": "apple_10k.pdf",
            "chunk_index": 2,
            "source": "sec.gov",
            "score": 0.028,
        },
    ]


@pytest.fixture
def mock_retrieval_service(mock_search_results):
    with patch(
        "app.features.retrieval.router.RetrievalService"
    ) as mock_cls:
        mock_service = AsyncMock()
        mock_service.search.return_value = mock_search_results
        mock_cls.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_deps():
    with patch("app.features.retrieval.router.get_db") as mock_db, \
         patch("app.features.retrieval.router.get_qdrant") as mock_qdrant:
        mock_db.return_value = AsyncMock()
        mock_qdrant.return_value = AsyncMock()
        yield


@pytest.mark.asyncio
async def test_search_returns_200(mock_retrieval_service, mock_deps):
    """Valid query should return 200 with results"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/retrieval/search",
            json={"query": "Apple revenue Q3", "top_n": 5},
        )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


@pytest.mark.asyncio
async def test_search_returns_correct_schema(mock_retrieval_service, mock_deps):
    """Response must contain results list and query echo"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/retrieval/search",
            json={"query": "Apple revenue Q3", "top_n": 5},
        )
    data = response.json()
    assert "results" in data
    assert "query" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_search_result_has_correct_fields(mock_retrieval_service, mock_deps):
    """Each result must have chunk_text, file_name, score, source"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/retrieval/search",
            json={"query": "Apple revenue Q3", "top_n": 5},
        )
    result = response.json()["results"][0]
    assert "chunk_text" in result
    assert "file_name" in result
    assert "score" in result
    assert "source" in result


@pytest.mark.asyncio
async def test_search_empty_query_returns_422(mock_deps):
    """Empty query should return 422"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/retrieval/search",
            json={"query": "", "top_n": 5},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_missing_query_returns_422(mock_deps):
    """Missing query field should return 422"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/retrieval/search",
            json={"top_n": 5},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_echoes_query(mock_retrieval_service, mock_deps):
    """Response should echo back the original query"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/retrieval/search",
            json={"query": "Apple revenue Q3", "top_n": 5},
        )
    assert response.json()["query"] == "Apple revenue Q3"


@pytest.mark.asyncio
async def test_search_default_top_n(mock_retrieval_service, mock_deps):
    """top_n should default to 5 if not provided"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/retrieval/search",
            json={"query": "Apple revenue Q3"},
        )
    assert response.status_code == 200