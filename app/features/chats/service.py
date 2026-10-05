from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.features.chats.models import Chat, ChatMessage

log = logger.getChild("chats")

TITLE_MAX = 60
LIST_LIMIT = 200


def _clean(text: str) -> str:
    # Postgres text columns reject NUL bytes outright.
    return text.replace("\x00", "").strip()


def title_from_query(query: str) -> str:
    """A chat has no name of its own, so use its first question, cut at a word boundary."""
    first_line = _clean(query).split("\n", 1)[0].strip()
    if len(first_line) <= TITLE_MAX:
        return first_line or "New chat"
    return first_line[:TITLE_MAX].rsplit(" ", 1)[0] + "…"


class ChatService:
    """Every query is scoped to the owner: a chat that isn't yours behaves as if it doesn't exist."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_chats(self, owner_id: int) -> list[Chat]:
        result = await self.db.execute(
            select(Chat).where(Chat.owner_id == owner_id).order_by(Chat.updated_at.desc()).limit(LIST_LIMIT)
        )
        return list(result.scalars().all())

    async def get_chat(self, chat_id: int, owner_id: int) -> Chat | None:
        result = await self.db.execute(select(Chat).where(Chat.id == chat_id, Chat.owner_id == owner_id))
        return result.scalar_one_or_none()

    async def get_messages(self, chat_id: int) -> list[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id)
        )
        return list(result.scalars().all())

    async def recent_history(self, chat_id: int, limit: int) -> list[dict]:
        """The last `limit` messages of a chat, oldest first, as {role, content}.

        Call it BEFORE start_turn(), or the question being asked is included.
        """
        result = await self.db.execute(
            select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id.desc()).limit(limit)
        )
        return [{"role": m.role, "content": m.content} for m in reversed(result.scalars().all())]

    async def get_assistant_message(self, message_id: int, owner_id: int) -> ChatMessage | None:
        """A saved answer, only if it belongs to one of the owner's chats."""
        result = await self.db.execute(
            select(ChatMessage)
            .join(Chat, Chat.id == ChatMessage.chat_id)
            .where(ChatMessage.id == message_id, ChatMessage.role == "assistant", Chat.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def delete_chat(self, chat_id: int, owner_id: int) -> bool:
        # Messages go with it: chat_messages.chat_id is ON DELETE CASCADE.
        result = await self.db.execute(delete(Chat).where(Chat.id == chat_id, Chat.owner_id == owner_id))
        return result.rowcount > 0

    async def start_turn(self, chat_id: int | None, owner_id: int, query: str) -> int:
        """Records the question, creating the chat if this is its first one, and COMMITS.

        The commit is deliberate: the answer is written later from a different
        session (save_answer), after the response has started streaming, and
        that session can only reference a chat that is already committed.
        """
        if chat_id is None:
            chat = Chat(owner_id=owner_id, title=title_from_query(query))
            self.db.add(chat)
            await self.db.flush()
            chat_id = chat.id
        self.db.add(ChatMessage(chat_id=chat_id, role="user", content=_clean(query)))
        await self.db.commit()
        return chat_id


async def save_answer(chat_id: int, content: str, sources: list[dict], search_query: str | None = None) -> None:
    """Stores the finished answer with the passages it came from.

    Runs from the streaming generator, whose request-scoped session is no
    longer usable, so it opens its own. Never raises: a failure here (e.g. the
    chat was deleted while the answer streamed) must not break a response the
    user has already received.
    """
    content = _clean(content)
    if not content:
        return
    try:
        async with AsyncSessionLocal() as session:
            session.add(ChatMessage(chat_id=chat_id, role="assistant", content=content, sources=sources, search_query=search_query))
            await session.execute(update(Chat).where(Chat.id == chat_id).values(updated_at=func.now()))
            await session.commit()
    except Exception as e:
        log.error(f"Could not save the answer for chat {chat_id}: {e}")
