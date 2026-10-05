import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient

from app.core.auth import UserScope, get_user_scope
from app.core.config import settings
from app.core.database import get_db
from app.core.qdrant import get_qdrant
from app.core.rate_limit import user_rate_limit
from app.core.logging import logger
from app.features.chats.service import ChatService, save_answer
from app.features.generation.history import HISTORY_MESSAGES, standalone_query
from app.features.retrieval.service import RetrievalService
from app.features.generation.service import GenerationService
from app.tasks.audit import process_query_audit

router = APIRouter(prefix="/api/v1/generation", tags=["generation"])

log = logger.getChild("generation.router")


class GenerateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_n: int = Field(default=5, ge=1, le=20)
    # Continue an existing chat. Omit it to start a new one; its id comes back
    # in the X-Chat-Id response header.
    chat_id: int | None = None


async def stream_and_audit(
    query: str,
    search_query: str,
    history: list[dict],
    chunks: list[dict],
    client_id: str,
    t0: float,
    chat_id: int,
) -> AsyncGenerator[str, None]:
    generation_service = GenerationService()
    full_answer = []

    async for token in generation_service.stream(
        query=search_query,
        chunks=chunks,
        history=history,
        asked=query,
    ):
        full_answer.append(token)
        yield token

    duration_ms = (time.perf_counter() - t0) * 1000
    answer = "".join(full_answer)

    await save_answer(chat_id, answer, chunks, search_query)

    log.info(f"Firing audit task for query: {query[:50]}...")
    process_query_audit.delay(
        query=query,
        answer=answer,
        chunks=chunks,
        model_used=settings.llm_model,
        embed_model_used=settings.embed_model,
        duration_ms=duration_ms,
        client_id=client_id,
        # Scored against what was searched for: "and services?" alone would
        # make the relevance score meaningless.
        search_query=search_query,
    )


@router.post(
    "/generate",
    dependencies=[Depends(user_rate_limit(settings.rate_limit_generate_per_minute, "generate"))],
)
async def generate(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    scope: UserScope = Depends(get_user_scope),
):
    t0 = time.perf_counter()
    chats = ChatService(db)
    history: list[dict] = []
    if request.chat_id is not None:
        if await chats.get_chat(request.chat_id, scope.user_id) is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        # Before start_turn(), so it holds only the earlier messages.
        history = await chats.recent_history(request.chat_id, HISTORY_MESSAGES)
    # A follow-up is rewritten into a standalone question for the search; a first question is searched as typed.
    search_query = await standalone_query(history, request.query)

    # Retrieval runs before the response starts: once streaming has begun the
    # status is already 200, so a failure here (e.g. the embedding provider's
    # rate limit) could only show up as a silently truncated answer.
    chunks = await RetrievalService(db=db, qdrant=qdrant).search(
        query=search_query,
        top_n=request.top_n,
        owner_id=scope.user_id,
        is_admin=scope.is_admin,
    )
    # After retrieval, so a failed search leaves no empty chat behind.
    chat_id = await chats.start_turn(request.chat_id, scope.user_id, request.query)
    return StreamingResponse(
        stream_and_audit(
            query=request.query,
            search_query=search_query,
            history=history,
            chunks=chunks,
            client_id=str(scope.user_id),
            t0=t0,
            chat_id=chat_id,
        ),
        media_type="text/plain",
        headers={"X-Chat-Id": str(chat_id)},
    )