from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient
import json

from app.core.database import get_db
from app.core.qdrant import get_qdrant
from app.core.logging import logger
from app.features.ingestion.service import IngestionService

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    source: str = Form(...),
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted",
        )

    file_bytes = await file.read()

    async def progress_stream():
        service = IngestionService(db=db, qdrant=qdrant)
        try:
            async for event in service.ingest_with_progress(
                file_bytes=file_bytes,
                file_name=file.filename,
                source=source,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        progress_stream(),
        media_type="text/event-stream",
    )