from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient
import json
import time

from app.core.auth import TokenUser, get_current_user
from app.core.config import settings
from app.core.database import get_db, AsyncSessionLocal
from app.core.qdrant import get_qdrant
from app.core.logging import logger
from app.features.ingestion.service import IngestionService
from app.features.ingestion.document_service import DocumentService
from app.tasks.audit import process_ingestion_audit

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    source: str = Form(...),
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    current_user: TokenUser = Depends(get_current_user),
):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted",
        )

    doc_service = DocumentService(db=db, qdrant=qdrant)
    if await doc_service.file_exists(file.filename):
        raise HTTPException(
            status_code=409,
            detail=f"{file.filename} has already been ingested. Delete it first to re-ingest.",
        )

    file_bytes = await file.read()
    file_name = file.filename
    file_size = len(file_bytes)
    client_id = current_user.sub
    t0 = time.perf_counter()

    async def progress_stream():
        status = "success"
        error_message = None
        chunks_ingested = 0

        try:
            async with AsyncSessionLocal() as stream_session:
                service = IngestionService(db=stream_session, qdrant=qdrant)
                async for event in service.ingest_with_progress(
                    file_bytes=file_bytes,
                    file_name=file_name,
                    source=source,
                ):
                    if event["status"] == "done":
                        chunks_ingested = event["chunks_ingested"]
                    yield f"data: {json.dumps(event)}\n\n"

        except ValueError as e:
            status = "error"
            error_message = str(e)
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

        finally:
            duration_ms = (time.perf_counter() - t0) * 1000
            process_ingestion_audit.delay(
                file_name=file_name,
                source=source,
                chunks_ingested=chunks_ingested,
                file_size_bytes=file_size,
                embed_model_used=settings.ollama_embed_model,
                duration_ms=duration_ms,
                client_id=client_id,
                status=status,
                error_message=error_message,
            )

    return StreamingResponse(
        progress_stream(),
        media_type="text/event-stream",
    )


@router.get("/documents")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    current_user: TokenUser = Depends(get_current_user),
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
    current_user: TokenUser = Depends(get_current_user),
):
    service = DocumentService(db=db, qdrant=qdrant)
    result = await service.delete_document(file_name=file_name)
    if result["chunks_deleted"] == 0:
        raise HTTPException(
            status_code=404,
            detail=f"{file_name} not found",
        )
    return result