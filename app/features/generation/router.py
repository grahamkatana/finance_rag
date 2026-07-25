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


# 1. Request schema
class GenerateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_n: int = Field(default=5, ge=1, le=20)


# 2. Stream wrapper
async def token_stream(
    query: str,
    top_n: int,
    db: AsyncSession,
    qdrant: AsyncQdrantClient,
) -> AsyncGenerator[str, None]:
    """
    Full RAG pipeline as an async generator:
    retrieve → build prompt → stream tokens
    """
    # Step 1: Retrieve relevant chunks
    retrieval_service = RetrievalService(db=db, qdrant=qdrant)
    chunks = await retrieval_service.search(query=query, top_n=top_n)

    # Step 2: Stream generation over retrieved chunks
    generation_service = GenerationService()
    async for token in generation_service.stream(query=query, chunks=chunks):
        yield token


@router.post("/generate")
async def generate(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
):
    return StreamingResponse(
        token_stream(
            query=request.query,
            top_n=request.top_n,
            db=db,
            qdrant=qdrant,
        ),
        media_type="text/plain",
    )