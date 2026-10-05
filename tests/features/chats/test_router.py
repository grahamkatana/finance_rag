from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _chat(id=1, title="What was net sales?"):
    return MagicMock(id=id, title=title, created_at=datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc), updated_at=datetime(2026, 10, 5, 9, 5, tzinfo=timezone.utc))


def _message(id, role, content, sources=None, search_query=None):
    return MagicMock(id=id, role=role, content=content, sources=sources, search_query=search_query, created_at=datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc))


@pytest.fixture
def service():
    with patch("app.features.chats.router.ChatService") as mock_cls:
        svc = AsyncMock()
        mock_cls.return_value = svc
        yield svc


async def _call(method, path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path)


@pytest.mark.asyncio
async def test_list_chats_returns_only_the_callers_chats(service):
    service.list_chats.return_value = [_chat(2, "Second"), _chat(1, "First")]
    response = await _call("GET", "/api/v1/chats")
    assert response.status_code == 200
    assert [c["title"] for c in response.json()["chats"]] == ["Second", "First"]
    service.list_chats.assert_awaited_once_with(1)  # the fake user's id, never anyone else's


@pytest.mark.asyncio
async def test_get_chat_returns_messages_with_sources(service):
    sources = [{"file_name": "10k.pdf", "chunk_index": 3, "chunk_text": "t", "source": "sec.gov", "score": 0.03}]
    service.get_chat.return_value = _chat()
    service.get_messages.return_value = [_message(1, "user", "q"), _message(2, "assistant", "a", sources, "What was net sales?")]
    response = await _call("GET", "/api/v1/chats/1")
    assert response.status_code == 200
    body = response.json()
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][1]["sources"] == sources
    assert body["messages"][0]["sources"] is None
    assert body["messages"][1]["search_query"] == "What was net sales?"
    service.get_chat.assert_awaited_once_with(1, 1)


@pytest.mark.asyncio
async def test_get_chat_that_is_not_yours_is_404(service):
    service.get_chat.return_value = None
    response = await _call("GET", "/api/v1/chats/5")
    assert response.status_code == 404
    service.get_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_chat(service):
    service.delete_chat.return_value = True
    response = await _call("DELETE", "/api/v1/chats/3")
    assert response.status_code == 200
    assert response.json() == {"id": 3, "deleted": True}
    service.delete_chat.assert_awaited_once_with(3, 1)


@pytest.mark.asyncio
async def test_delete_chat_that_is_not_yours_is_404(service):
    service.delete_chat.return_value = False
    assert (await _call("DELETE", "/api/v1/chats/3")).status_code == 404


@pytest.mark.asyncio
async def test_admins_get_no_special_view_of_other_users_chats(service, admin_scope):
    """Chats are private even from admins (the Activity page is where admins audit questions)."""
    service.list_chats.return_value = []
    await _call("GET", "/api/v1/chats")
    service.list_chats.assert_awaited_once_with(1)
