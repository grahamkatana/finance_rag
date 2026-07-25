from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient
import json

from app.core.database import get_db, AsyncSessionLocal
from app.core.qdrant import get_qdrant
from app.core.logging import logger
from app.features.ingestion.service import IngestionService
from app.features.ingestion.document_service import DocumentService

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

    # 1. Duplicate check using the request session
    doc_service = DocumentService(db=db, qdrant=qdrant)
    if await doc_service.file_exists(file.filename):
        raise HTTPException(
            status_code=409,
            detail=f"{file.filename} has already been ingested. Delete it first to re-ingest.",
        )

    file_bytes = await file.read()
    file_name = file.filename

    # 2. Stream using a FRESH session — avoids session conflict
    async def progress_stream():
        async with AsyncSessionLocal() as stream_session:
            service = IngestionService(db=stream_session, qdrant=qdrant)
            try:
                async for event in service.ingest_with_progress(
                    file_bytes=file_bytes,
                    file_name=file_name,
                    source=source,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except ValueError as e:
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        progress_stream(),
        media_type="text/event-stream",
    )


@router.get("/documents")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
):
    service = DocumentService(db=db, qdrant=qdrant)
    documents = await service.list_documents()
    return {
        "documents": documents,
        "total": len(documents),
    }


@router.delete("/documents/{file_name}")
async def delete_document(
    file_name: str,
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
):
    service = DocumentService(db=db, qdrant=qdrant)
    result = await service.delete_document(file_name=file_name)
    if result["chunks_deleted"] == 0:
        raise HTTPException(
            status_code=404,
            detail=f"{file_name} not found",
        )
    return result