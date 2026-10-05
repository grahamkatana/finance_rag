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


@pytest.fixture(autouse=True)
def mock_chats():
    """Chat persistence needs a real database; these tests are about retrieval and streaming."""
    with patch("app.features.generation.router.ChatService") as mock_cls, \
         patch("app.features.generation.router.save_answer", new_callable=AsyncMock) as mock_save:
        service = AsyncMock()
        service.get_chat.return_value = MagicMock()  # any chat id belongs to the caller
        service.start_turn.return_value = 42
        service.recent_history.return_value = []  # no earlier messages unless a test says so
        mock_cls.return_value = service
        yield MagicMock(service=service, save_answer=mock_save)


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
            json={"query": "What was Apple revenue in Q3?"},
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
            json={"query": "What was Apple revenue in Q3?"},
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
            json={"query": "What was Apple revenue in Q3?"},
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
            json={"query": ""},
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
            json={},
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
            json={"query": "What was Apple revenue in Q3?"},
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
            json={"query": "What was Apple revenue in Q3?"},
        )
    assert mock_audit.delay.called


@pytest.mark.asyncio
async def test_generate_audit_receives_client_id(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """Audit task must receive client_id from JWT sub claim"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/generation/generate",
            json={"query": "What was Apple revenue in Q3?"},
        )
    call_kwargs = mock_audit.delay.call_args.kwargs
    assert call_kwargs["client_id"] == "1"


@pytest.mark.asyncio
async def test_generate_default_client_id(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """client_id always comes from JWT sub — never anonymous"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/generation/generate",
            json={"query": "What was Apple revenue in Q3?"},
        )
    call_kwargs = mock_audit.delay.call_args.kwargs
    assert call_kwargs["client_id"] == "1"


@pytest.mark.asyncio
async def test_generate_retrieval_failure_is_an_http_error_not_a_broken_stream(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps
):
    """Retrieval runs before streaming starts, so its failure reaches the client as a 503."""
    from app.features.retrieval.service import EmbeddingUnavailableError
    mock_retrieval_service.search.side_effect = EmbeddingUnavailableError("reduced rate limits of 3 RPM")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/generation/generate", json={"query": "net sales?"})
    assert response.status_code == 503
    assert "rate limit" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_starts_a_chat_and_returns_its_id(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps, mock_chats
):
    """Without a chat_id a new chat is created; its id is returned in X-Chat-Id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/generation/generate", json={"query": "What was net sales?"})
    assert response.headers["x-chat-id"] == "42"
    mock_chats.service.start_turn.assert_awaited_once_with(None, 1, "What was net sales?")
    mock_chats.service.get_chat.assert_not_awaited()  # nothing to check when starting a new chat


@pytest.mark.asyncio
async def test_generate_saves_the_finished_answer_with_its_sources(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps, mock_chats
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/generation/generate", json={"query": "q"})
    assert response.text == "Apple revenue grew 12% in Q3."
    chat_id, content, sources, search_query = mock_chats.save_answer.await_args.args
    assert (chat_id, content, search_query) == (42, "Apple revenue grew 12% in Q3.", "q")
    assert sources == mock_retrieval_service.search.return_value


@pytest.mark.asyncio
async def test_generate_continues_an_existing_chat(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps, mock_chats
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/generation/generate", json={"query": "q", "chat_id": 7})
    mock_chats.service.get_chat.assert_awaited_once_with(7, 1)
    mock_chats.service.start_turn.assert_awaited_once_with(7, 1, "q")


@pytest.mark.asyncio
async def test_generate_rejects_a_chat_that_is_not_yours(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps, mock_chats
):
    """Someone else's (or a missing) chat is a 404, and no search is spent on it."""
    mock_chats.service.get_chat.return_value = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/generation/generate", json={"query": "q", "chat_id": 999})
    assert response.status_code == 404
    mock_retrieval_service.search.assert_not_awaited()
    mock_chats.service.start_turn.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_failed_retrieval_leaves_no_empty_chat(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps, mock_chats
):
    from app.features.retrieval.service import EmbeddingUnavailableError
    mock_retrieval_service.search.side_effect = EmbeddingUnavailableError("rate limited")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/generation/generate", json={"query": "q"})
    assert response.status_code == 503
    mock_chats.service.start_turn.assert_not_awaited()


HISTORY = [
    {"role": "user", "content": "What was Apple's net sales in 2024?"},
    {"role": "assistant", "content": "$391.0 billion [Source 1]."},
]


@pytest.mark.asyncio
async def test_first_question_is_searched_as_typed_and_never_rewritten(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps, mock_chats
):
    with patch("app.features.generation.router.standalone_query", new_callable=AsyncMock) as condense:
        condense.side_effect = lambda history, query: query
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/generation/generate", json={"query": "What was net sales?"})
    condense.assert_awaited_once_with([], "What was net sales?")
    mock_chats.service.recent_history.assert_not_awaited()  # new chat: nothing to load
    assert mock_retrieval_service.search.await_args.kwargs["query"] == "What was net sales?"


@pytest.mark.asyncio
async def test_follow_up_is_rewritten_searched_and_answered_with_the_conversation(
    mock_retrieval_service, mock_audit, mock_deps, mock_chats
):
    """The rewrite drives the search; the answer model gets the history and both phrasings; the audit scores the rewrite."""
    mock_chats.service.recent_history.return_value = HISTORY
    seen = {}

    async def recording_stream(**kwargs):
        seen.update(kwargs)
        yield "Services were $96.2B."

    with patch("app.features.generation.router.standalone_query", new_callable=AsyncMock) as condense, \
         patch("app.features.generation.router.GenerationService") as gen_cls:
        condense.return_value = "What were Apple's services net sales in fiscal 2024?"
        gen_cls.return_value.stream = recording_stream
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/generation/generate", json={"query": "And services?", "chat_id": 7})

    assert response.status_code == 200
    mock_chats.service.recent_history.assert_awaited_once()
    assert mock_chats.service.recent_history.await_args.args[0] == 7
    condense.assert_awaited_once_with(HISTORY, "And services?")
    assert mock_retrieval_service.search.await_args.kwargs["query"] == "What were Apple's services net sales in fiscal 2024?"
    assert seen["query"] == "What were Apple's services net sales in fiscal 2024?"
    assert seen["asked"] == "And services?" and seen["history"] == HISTORY
    assert mock_chats.save_answer.await_args.args[3] == "What were Apple's services net sales in fiscal 2024?"
    audit = mock_audit.delay.call_args.kwargs
    assert audit["query"] == "And services?"  # what the user typed is what Activity shows
    assert audit["search_query"] == "What were Apple's services net sales in fiscal 2024?"


@pytest.mark.asyncio
async def test_history_is_read_before_the_new_question_is_saved(
    mock_retrieval_service, mock_generation_service, mock_audit, mock_deps, mock_chats
):
    """Otherwise the question being asked would be part of its own 'earlier conversation'."""
    order = []
    mock_chats.service.recent_history.side_effect = lambda *a: order.append("history") or []
    mock_chats.service.start_turn.side_effect = lambda *a: order.append("start_turn") or 42
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/generation/generate", json={"query": "q", "chat_id": 7})
    assert order == ["history", "start_turn"]

