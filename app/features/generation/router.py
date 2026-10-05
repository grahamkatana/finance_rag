import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
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
from app.features.retrieval.service import RetrievalService
from app.features.generation.service import GenerationService
from app.tasks.audit import process_query_audit

router = APIRouter(prefix="/api/v1/generation", tags=["generation"])

log = logger.getChild("generation.router")


class GenerateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_n: int = Field(default=5, ge=1, le=20)


async def stream_and_audit(
    query: str,
    chunks: list[dict],
    client_id: str,
    t0: float,
) -> AsyncGenerator[str, None]:
    generation_service = GenerationService()
    full_answer = []

    async for token in generation_service.stream(
        query=query,
        chunks=chunks,
    ):
        full_answer.append(token)
        yield token

    duration_ms = (time.perf_counter() - t0) * 1000
    answer = "".join(full_answer)

    log.info(f"Firing audit task for query: {query[:50]}...")
    process_query_audit.delay(
        query=query,
        answer=answer,
        chunks=chunks,
        model_used=settings.llm_model,
        embed_model_used=settings.embed_model,
        duration_ms=duration_ms,
        client_id=client_id,
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
    # Retrieval runs before the response starts: once streaming has begun the
    # status is already 200, so a failure here (e.g. the embedding provider's
    # rate limit) could only show up as a silently truncated answer.
    chunks = await RetrievalService(db=db, qdrant=qdrant).search(
        query=request.query,
        top_n=request.top_n,
        owner_id=scope.user_id,
        is_admin=scope.is_admin,
    )
    return StreamingResponse(
        stream_and_audit(
            query=request.query,
            chunks=chunks,
            client_id=str(scope.user_id),
            t0=t0,
        ),
        media_type="text/plain",
    )