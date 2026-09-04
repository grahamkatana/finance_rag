from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient

from app.core.auth import UserScope, get_user_scope
from app.core.database import get_db
from app.core.qdrant import get_qdrant
from app.features.retrieval.service import RetrievalService

router = APIRouter(prefix="/api/v1/retrieval", tags=["retrieval"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_n: int = Field(default=5, ge=1, le=20)


class ChunkResult(BaseModel):
    chunk_text: str
    file_name: str
    chunk_index: int
    source: str
    score: float


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[ChunkResult]


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    scope: UserScope = Depends(get_user_scope),
):
    service = RetrievalService(db=db, qdrant=qdrant)

    try:
        results = await service.search(
            query=request.query,
            top_n=request.top_n,
            owner_id=scope.user_id,
            is_admin=scope.is_admin,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return SearchResponse(
        query=request.query,
        total=len(results),
        results=[ChunkResult(**r) for r in results],
    )