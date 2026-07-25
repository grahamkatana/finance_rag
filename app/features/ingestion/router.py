from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient

from app.core.database import get_db
from app.core.qdrant import get_qdrant
from app.features.ingestion.service import IngestionService

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    source: str = Form(...),
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
):
    # 1. Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted",
        )

    # 2. Read file bytes
    file_bytes = await file.read()

    # 3. Run ingestion pipeline
    service = IngestionService(db=db, qdrant=qdrant)
    try:
        result = await service.ingest(
            file_bytes=file_bytes,
            file_name=file.filename,
            source=source,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result