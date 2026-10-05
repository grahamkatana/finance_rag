"""
Turn a user's past questions into saved chats.

Questions asked before chats existed were recorded only in the audit trail
(with their answer and the passages used), so they never appeared in the chat
list. This copies them across, one chat per question, keeping their original
times, so the history shows up:

    uv run python -m app.backfill_chats --username gka --dry-run   # count only
    uv run python -m app.backfill_chats --username gka

Safe to re-run: a question that already has a chat (same owner, same time) is
skipped. To undo, delete the chats from the sidebar.
"""

import argparse
import asyncio
import json

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.database.models import AuditQueryEvent
from app.features.auth.service import get_user_by_username
from app.features.chats.models import Chat, ChatMessage
from app.features.chats.service import title_from_query


def _sources(raw: str) -> list:
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


async def backfill(db, user_id: int, dry_run: bool = False) -> tuple[int, int]:
    """Returns (created, skipped)."""
    events = (
        await db.execute(
            select(AuditQueryEvent).where(AuditQueryEvent.client_id == str(user_id)).order_by(AuditQueryEvent.created_at)
        )
    ).scalars().all()
    have = set((await db.execute(select(Chat.created_at).where(Chat.owner_id == user_id))).scalars().all())

    created = skipped = 0
    for event in events:
        if event.created_at in have or not (event.answer or "").strip():
            skipped += 1
            continue
        created += 1
        if dry_run:
            continue
        chat = Chat(owner_id=user_id, title=title_from_query(event.query), created_at=event.created_at, updated_at=event.created_at)
        db.add(chat)
        await db.flush()
        db.add(ChatMessage(chat_id=chat.id, role="user", content=event.query.replace("\x00", ""), created_at=event.created_at))
        db.add(ChatMessage(chat_id=chat.id, role="assistant", content=event.answer.replace("\x00", ""), sources=_sources(event.retrieved_chunks), created_at=event.created_at))
    if not dry_run:
        await db.commit()
    return created, skipped


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(args.username, db)
        if user is None:
            raise SystemExit(f"No user named '{args.username}'.")
        created, skipped = await backfill(db, user.id, args.dry_run)
    print(f"{'Would create' if args.dry_run else 'Created'} {created} chat(s) for '{args.username}'; skipped {skipped} (already there or no answer).")


if __name__ == "__main__":
    asyncio.run(main())
