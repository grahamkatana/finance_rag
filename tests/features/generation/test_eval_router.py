import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
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


@pytest.mark.asyncio
async def test_eval_retrieval_is_scoped_to_the_caller(
    mock_deps, mock_retrieval_service, mock_eval_service
):
    """The judge must only see chunks the caller can access (same as /generate)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/generation/eval",
            json={"query": "What was net sales?", "answer": "391 billion."},
        )
    kwargs = mock_retrieval_service.search.call_args.kwargs
    assert kwargs["owner_id"] == 1
    assert kwargs["is_admin"] is False


@pytest.mark.asyncio
async def test_eval_judge_failure_returns_readable_503(
    mock_deps, mock_retrieval_service, mock_eval_service
):
    """A judge-provider error (quota, plan, outage) is a 503 with a message, not a bare 500."""
    mock_eval_service.evaluate.side_effect = RuntimeError("this model is not included in your free usage")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/generation/eval",
            json={"query": "What was net sales?", "answer": "391 billion."},
        )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "scoring model is unavailable" in detail
    assert "free usage" not in detail  # the provider's message is logged, not shown to users


@pytest.fixture
def saved_answer():
    with patch("app.features.generation.eval_router.ChatService") as mock_cls:
        service = AsyncMock()
        service.get_assistant_message.return_value = MagicMock(
            content="Services were $96.2B (saved answer).",
            sources=[{"chunk_text": "Services net sales were $96,169 million.", "file_name": "10k.pdf", "chunk_index": 7}],
            search_query="What were Apple's services net sales in fiscal 2024?",
        )
        mock_cls.return_value = service
        yield service


@pytest.mark.asyncio
async def test_eval_of_a_saved_answer_uses_its_own_passages_and_search_query(
    mock_deps, mock_retrieval_service, mock_eval_service, saved_answer
):
    """For a follow-up, searching again with the typed words would find other passages and give a misleading score."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/generation/eval",
            json={"query": "And services?", "answer": "ignored: the saved answer is used", "message_id": 12},
        )
    assert response.status_code == 200
    assert response.json()["query"] == "And services?"  # echoes what the caller sent
    saved_answer.get_assistant_message.assert_awaited_once_with(12, 1)
    mock_retrieval_service.search.assert_not_awaited()  # no search, so no embedding call either
    kwargs = mock_eval_service.evaluate.await_args.kwargs
    assert kwargs["query"] == "What were Apple's services net sales in fiscal 2024?"
    assert kwargs["answer"] == "Services were $96.2B (saved answer)."
    assert kwargs["chunks"][0]["file_name"] == "10k.pdf"


@pytest.mark.asyncio
async def test_eval_of_an_answer_that_is_not_yours_is_404(
    mock_deps, mock_retrieval_service, mock_eval_service, saved_answer
):
    saved_answer.get_assistant_message.return_value = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/generation/eval", json={"query": "q", "answer": "a", "message_id": 999},
        )
    assert response.status_code == 404
    mock_eval_service.evaluate.assert_not_awaited()

