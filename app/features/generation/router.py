import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient

from app.core.auth import TokenUser, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.qdrant import get_qdrant
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
    top_n: int,
    client_id: str,
    db: AsyncSession,
    qdrant: AsyncQdrantClient,
) -> AsyncGenerator[str, None]:
    t0 = time.perf_counter()

    retrieval_service = RetrievalService(db=db, qdrant=qdrant)
    chunks = await retrieval_service.search(query=query, top_n=top_n)

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
        model_used=settings.ollama_llm_model,
        embed_model_used=settings.ollama_embed_model,
        duration_ms=duration_ms,
        client_id=client_id,
    )


@router.post("/generate")
async def generate(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    current_user: TokenUser = Depends(get_current_user),
):
    return StreamingResponse(
        stream_and_audit(
            query=request.query,
            top_n=request.top_n,
            client_id=current_user.sub,
            db=db,
            qdrant=qdrant,
        ),
        media_type="text/plain",
    )