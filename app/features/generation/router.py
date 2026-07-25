from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient

from app.core.database import get_db
from app.core.qdrant import get_qdrant
from app.features.retrieval.service import RetrievalService
from app.features.generation.service import GenerationService

router = APIRouter(prefix="/api/v1/generation", tags=["generation"])


class GenerateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_n: int = Field(default=5, ge=1, le=20)


@router.post("/generate")
async def generate(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
):
    # 1. Do retrieval BEFORE streaming starts
    # so DB session is still open and valid
    retrieval_service = RetrievalService(db=db, qdrant=qdrant)
    chunks = await retrieval_service.search(
        query=request.query,
        top_n=request.top_n,
    )

    # 2. Build stream generator with chunks already retrieved
    async def stream_tokens() -> AsyncGenerator[str, None]:
        generation_service = GenerationService()
        async for token in generation_service.stream(
            query=request.query,
            chunks=chunks,
        ):
            yield token

    # 3. Stream only the generation — no DB access inside
    return StreamingResponse(
        stream_tokens(),
        media_type="text/plain",
    )