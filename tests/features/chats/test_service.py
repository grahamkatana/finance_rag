from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.features.chats.models import Chat, ChatMessage
from app.features.chats.service import ChatService, save_answer, title_from_query


def test_title_is_the_first_line_cut_at_a_word_boundary():
    assert title_from_query("What was net sales?") == "What was net sales?"
    long = "How did the company's gross margin change over the last three fiscal years and why"
    title = title_from_query(long)
    assert title.endswith("…") and len(title) <= 61 and not title[:-1].endswith(" ")
    assert title_from_query("First line\nsecond line") == "First line"
    assert title_from_query("   \x00  ") == "New chat"


def _db():
    db = AsyncMock()
    db.add = MagicMock()  # Session.add is synchronous

    async def assign_id():
        for call in db.add.call_args_list:
            if isinstance(call.args[0], Chat):
                call.args[0].id = 11

    db.flush.side_effect = assign_id
    return db


@pytest.mark.asyncio
async def test_start_turn_creates_the_chat_records_the_question_and_commits():
    db = _db()
    chat_id = await ChatService(db).start_turn(None, owner_id=7, query="What was net sales?")
    chat, message = [c.args[0] for c in db.add.call_args_list]
    assert chat_id == 11
    assert isinstance(chat, Chat) and (chat.owner_id, chat.title) == (7, "What was net sales?")
    assert isinstance(message, ChatMessage) and (message.chat_id, message.role, message.content) == (11, "user", "What was net sales?")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_turn_on_an_existing_chat_adds_only_a_message():
    db = _db()
    chat_id = await ChatService(db).start_turn(5, owner_id=7, query="And the year before?\x00")
    (message,) = [c.args[0] for c in db.add.call_args_list]
    assert chat_id == 5 and message.chat_id == 5 and message.content == "And the year before?"  # NUL stripped
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_every_lookup_is_scoped_to_the_owner():
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None), rowcount=0)
    service = ChatService(db)
    await service.get_chat(3, owner_id=7)
    await service.delete_chat(3, owner_id=7)
    for call in db.execute.await_args_list:
        sql = str(call.args[0].compile(compile_kwargs={"literal_binds": True}))
        assert "owner_id = 7" in sql, sql


@pytest.mark.asyncio
async def test_save_answer_stores_content_and_sources_in_its_own_session():
    session = AsyncMock()
    session.add = MagicMock()
    with patch("app.features.chats.service.AsyncSessionLocal") as factory:
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        await save_answer(9, "Net sales were $391B.\x00", [{"file_name": "10k.pdf"}])
    (message,) = [c.args[0] for c in session.add.call_args_list]
    assert (message.chat_id, message.role, message.content, message.sources) == (9, "assistant", "Net sales were $391B.", [{"file_name": "10k.pdf"}])
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_answer_ignores_an_empty_answer():
    with patch("app.features.chats.service.AsyncSessionLocal") as factory:
        await save_answer(9, "  ", [])
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_save_answer_never_raises():
    """If the chat was deleted while the answer streamed, the user's response must not break."""
    with patch("app.features.chats.service.AsyncSessionLocal", side_effect=RuntimeError("fk violation")):
        await save_answer(9, "An answer", [])


@pytest.mark.asyncio
async def test_recent_history_is_the_last_messages_oldest_first():
    """Fetched newest-first with a limit, then put back in reading order."""
    newest_first = [MagicMock(role="assistant", content="third"), MagicMock(role="user", content="second"), MagicMock(role="assistant", content="first")]
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=newest_first))))
    history = await ChatService(db).recent_history(chat_id=4, limit=3)
    assert history == [{"role": "assistant", "content": "first"}, {"role": "user", "content": "second"}, {"role": "assistant", "content": "third"}]
    sql = str(db.execute.await_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    assert "chat_id = 4" in sql and "DESC" in sql and "LIMIT 3" in sql


@pytest.mark.asyncio
async def test_a_saved_answer_is_only_found_through_its_owners_chat():
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    assert await ChatService(db).get_assistant_message(12, owner_id=7) is None
    sql = str(db.execute.await_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    assert "chats.owner_id = 7" in sql and "chat_messages.role = 'assistant'" in sql and "chat_messages.id = 12" in sql


@pytest.mark.asyncio
async def test_save_answer_keeps_the_search_query():
    session = AsyncMock()
    session.add = MagicMock()
    with patch("app.features.chats.service.AsyncSessionLocal") as factory:
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        await save_answer(9, "Services were $96.2B.", [], "What were Apple's services net sales in fiscal 2024?")
    (message,) = [c.args[0] for c in session.add.call_args_list]
    assert message.search_query == "What were Apple's services net sales in fiscal 2024?"
