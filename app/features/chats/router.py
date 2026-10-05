from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserScope, get_user_scope
from app.core.database import get_db
from app.features.chats.service import ChatService

router = APIRouter(prefix="/api/v1/chats", tags=["chats"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")


def _chat_dict(chat) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at.isoformat() if chat.created_at else None,
        "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
    }


@router.get("")
async def list_chats(
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_user_scope),
):
    """Your chats, most recently active first. Chats are private: admins see only their own here too."""
    chats = await ChatService(db).list_chats(scope.user_id)
    return {"chats": [_chat_dict(c) for c in chats], "total": len(chats)}


@router.get("/{chat_id}")
async def get_chat(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_user_scope),
):
    service = ChatService(db)
    chat = await service.get_chat(chat_id, scope.user_id)
    if chat is None:
        raise NOT_FOUND
    messages = await service.get_messages(chat_id)
    return {
        **_chat_dict(chat),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "search_query": m.search_query,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_user_scope),
):
    if not await ChatService(db).delete_chat(chat_id, scope.user_id):
        raise NOT_FOUND
    return {"id": chat_id, "deleted": True}
