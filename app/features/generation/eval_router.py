from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient

from app.core.auth import UserScope, get_user_scope
from app.features.chats.service import ChatService
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger
from app.core.qdrant import get_qdrant
from app.core.rate_limit import user_rate_limit
from app.features.retrieval.service import RetrievalService
from app.features.generation.eval import EvalService

router = APIRouter(prefix="/api/v1/generation", tags=["evaluation"])


class EvalRequest(BaseModel):
    query: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    top_n: int = Field(default=5, ge=1, le=20)
    # A saved answer in one of your chats. When given, it is scored against the
    # passages it was actually built from (and the question that was searched
    # for), instead of searching again with `query`, which for a follow-up like
    # "and services?" would find different passages and give a misleading score.
    message_id: int | None = None


class EvalResponse(BaseModel):
    query: str
    faithfulness: float
    relevance: float
    chunks_evaluated: int


@router.post(
    "/eval",
    response_model=EvalResponse,
    dependencies=[Depends(user_rate_limit(settings.rate_limit_eval_per_minute, "eval"))],
)
async def evaluate(
    request: EvalRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    scope: UserScope = Depends(get_user_scope),
):
    query, answer = request.query, request.answer
    if request.message_id is not None:
        saved = await ChatService(db).get_assistant_message(request.message_id, scope.user_id)
        if saved is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
        chunks = saved.sources or []
        query, answer = saved.search_query or request.query, saved.content
    else:
        retrieval_service = RetrievalService(db=db, qdrant=qdrant)
        chunks = await retrieval_service.search(
            query=request.query,
            top_n=request.top_n,
            # Same scoping as /generate: the judge must only see chunks the
            # caller could have been answered from, never another user's files.
            owner_id=scope.user_id,
            is_admin=scope.is_admin,
        )

    eval_service = EvalService()
    try:
        result = await eval_service.evaluate(
            query=query,
            chunks=chunks,
            answer=answer,
        )
    except Exception as e:
        # The judge is an external model (any provider): a quota, plan or
        # outage error there is not this API's bug, so say so rather than
        # returning a bare 500. The provider's own message stays in the log.
        logger.getChild("generation.eval").error(f"Judge model {settings.judge_model} failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The scoring model is unavailable right now, so this answer could not be checked. Please try again later.",
        )

    return EvalResponse(**{**result, "query": request.query})