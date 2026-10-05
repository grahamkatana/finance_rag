import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.backfill_chats import backfill
from app.features.chats.models import Chat, ChatMessage


def _event(minute, query="What was net sales?", answer="391B [Source 1].", chunks=None):
    return MagicMock(created_at=datetime(2026, 10, 5, 9, minute, tzinfo=timezone.utc), query=query, answer=answer,
                     retrieved_chunks=json.dumps(chunks if chunks is not None else [{"file_name": "10k.pdf", "chunk_index": 1, "chunk_text": "t"}]))


def _db(events, existing_times=()):
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=events)))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=list(existing_times))))),
    ]
    db.flush.side_effect = lambda: [setattr(c.args[0], "id", 100 + i) for i, c in enumerate(db.add.call_args_list) if isinstance(c.args[0], Chat)] and None
    return db


@pytest.mark.asyncio
async def test_each_past_question_becomes_a_chat_with_its_answer_sources_and_original_time():
    db = _db([_event(8), _event(9, query="What are the risks?", answer="Many.")])
    created, skipped = await backfill(db, user_id=2)
    assert (created, skipped) == (2, 0)
    added = [c.args[0] for c in db.add.call_args_list]
    chats = [a for a in added if isinstance(a, Chat)]
    messages = [a for a in added if isinstance(a, ChatMessage)]
    assert [c.owner_id for c in chats] == [2, 2] and chats[1].title == "What are the risks?"
    assert chats[0].created_at == datetime(2026, 10, 5, 9, 8, tzinfo=timezone.utc)
    assert [(m.role, m.content) for m in messages[:2]] == [("user", "What was net sales?"), ("assistant", "391B [Source 1].")]
    assert messages[1].sources[0]["file_name"] == "10k.pdf"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_dry_run_counts_but_writes_nothing():
    db = _db([_event(8), _event(9)])
    assert await backfill(db, 2, dry_run=True) == (2, 0)
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_running_it_twice_does_not_duplicate_chats():
    already = [datetime(2026, 10, 5, 9, 8, tzinfo=timezone.utc)]
    db = _db([_event(8), _event(9)], existing_times=already)
    assert await backfill(db, 2) == (1, 1)


@pytest.mark.asyncio
async def test_a_question_with_no_answer_is_skipped_and_bad_source_data_does_not_stop_it():
    broken = _event(10)
    broken.retrieved_chunks = "{not json"
    db = _db([_event(8, answer="  "), broken])
    assert await backfill(db, 2) == (1, 1)
    messages = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], ChatMessage)]
    assert messages[1].sources == []
