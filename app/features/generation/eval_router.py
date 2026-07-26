from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient

from app.core.auth import TokenUser, get_current_user
from app.core.database import get_db
from app.core.qdrant import get_qdrant
from app.features.retrieval.service import RetrievalService
from app.features.generation.eval import EvalService

router = APIRouter(prefix="/api/v1/generation", tags=["evaluation"])


class EvalRequest(BaseModel):
    query: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    top_n: int = Field(default=5, ge=1, le=20)


class EvalResponse(BaseModel):
    query: str
    faithfulness: float
    relevance: float
    chunks_evaluated: int


@router.post("/eval", response_model=EvalResponse)
async def evaluate(
    request: EvalRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    current_user: TokenUser = Depends(get_current_user),
):
    retrieval_service = RetrievalService(db=db, qdrant=qdrant)
    chunks = await retrieval_service.search(
        query=request.query,
        top_n=request.top_n,
    )

    eval_service = EvalService()
    result = await eval_service.evaluate(
        query=request.query,
        chunks=chunks,
        answer=request.answer,
    )

    return EvalResponse(**result)