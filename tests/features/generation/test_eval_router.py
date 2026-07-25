import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


@pytest.fixture
def mock_eval_result():
    return {
        "query": "What was Apple net sales in 2024?",
        "faithfulness": 0.85,
        "relevance": 0.90,
        "chunks_evaluated": 3,
    }


@pytest.fixture
def mock_retrieval_service():
    with patch("app.features.generation.eval_router.RetrievalService") as mock_cls:
        mock_service = AsyncMock()
        mock_service.search.return_value = [
            {
                "chunk_text": "Apple net sales were 391 billion.",
                "file_name": "apple_10k.pdf",
                "chunk_index": 0,
                "source": "sec.gov",
                "score": 0.032,
            }
        ]
        mock_cls.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_eval_service(mock_eval_result):
    with patch("app.features.generation.eval_router.EvalService") as mock_cls:
        mock_service = AsyncMock()
        mock_service.evaluate.return_value = mock_eval_result
        mock_cls.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_deps():
    with patch("app.features.generation.eval_router.get_db") as mock_db, \
         patch("app.features.generation.eval_router.get_qdrant") as mock_qdrant:
        mock_db.return_value = AsyncMock()
        mock_qdrant.return_value = AsyncMock()
        yield


@pytest.mark.asyncio
async def test_eval_returns_200(
    mock_retrieval_service, mock_eval_service, mock_deps
):
    """Valid eval request should return 200"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/eval",
            json={
                "query": "What was Apple net sales in 2024?",
                "answer": "Apple net sales were 391 billion dollars.",
            },
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_eval_returns_correct_schema(
    mock_retrieval_service, mock_eval_service, mock_deps
):
    """Response must contain faithfulness, relevance and query"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/eval",
            json={
                "query": "What was Apple net sales in 2024?",
                "answer": "Apple net sales were 391 billion dollars.",
            },
        )
    data = response.json()
    assert "faithfulness" in data
    assert "relevance" in data
    assert "query" in data
    assert "chunks_evaluated" in data


@pytest.mark.asyncio
async def test_eval_scores_are_floats(
    mock_retrieval_service, mock_eval_service, mock_deps
):
    """Faithfulness and relevance must be floats"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/eval",
            json={
                "query": "What was Apple net sales in 2024?",
                "answer": "Apple net sales were 391 billion dollars.",
            },
        )
    data = response.json()
    assert isinstance(data["faithfulness"], float)
    assert isinstance(data["relevance"], float)


@pytest.mark.asyncio
async def test_eval_scores_in_range(
    mock_retrieval_service, mock_eval_service, mock_deps
):
    """Scores must be between 0.0 and 1.0"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/eval",
            json={
                "query": "What was Apple net sales in 2024?",
                "answer": "Apple net sales were 391 billion dollars.",
            },
        )
    data = response.json()
    assert 0.0 <= data["faithfulness"] <= 1.0
    assert 0.0 <= data["relevance"] <= 1.0


@pytest.mark.asyncio
async def test_eval_empty_query_returns_422(mock_deps):
    """Empty query should return 422"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/eval",
            json={
                "query": "",
                "answer": "Some answer.",
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_eval_missing_answer_returns_422(mock_deps):
    """Missing answer field should return 422"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/eval",
            json={"query": "What was Apple net sales?"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_eval_calls_retrieval(
    mock_retrieval_service, mock_eval_service, mock_deps
):
    """Eval must retrieve chunks for the query"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/generation/eval",
            json={
                "query": "What was Apple net sales in 2024?",
                "answer": "Apple net sales were 391 billion dollars.",
            },
        )
    assert mock_retrieval_service.search.called