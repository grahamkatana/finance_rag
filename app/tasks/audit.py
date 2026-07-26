import asyncio
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.celery import celery_app
from app.core.logging import logger
from app.database.audit import get_audit_session
from app.features.generation.eval import EvalService

log = logger.getChild("audit_task")


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="audit.process_query",
)
def process_query_audit(
    self,
    query: str,
    answer: str,
    chunks: list[dict],
    model_used: str,
    embed_model_used: str,
    duration_ms: float,
    client_id: str = "anonymous",
):
    try:
        log.info(f"Processing audit for query: {query[:50]}...")
        faithfulness, relevance = asyncio.run(
            _run_eval(query=query, answer=answer, chunks=chunks)
        )
        asyncio.run(
            _write_audit(
                query=query,
                answer=answer,
                chunks=chunks,
                faithfulness=faithfulness,
                relevance=relevance,
                model_used=model_used,
                embed_model_used=embed_model_used,
                duration_ms=duration_ms,
                client_id=client_id,
            )
        )
        log.info(
            f"Audit complete — faithfulness={faithfulness:.2f} "
            f"relevance={relevance:.2f}"
        )
        return {"faithfulness": faithfulness, "relevance": relevance}

    except Exception as exc:
        log.error(f"Audit task failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="audit.process_ingestion",
)
def process_ingestion_audit(
    self,
    file_name: str,
    source: str,
    chunks_ingested: int,
    file_size_bytes: int,
    embed_model_used: str,
    duration_ms: float,
    client_id: str = "anonymous",
    status: str = "success",
    error_message: str = None,
):
    try:
        log.info(f"Processing ingestion audit for: {file_name}")
        asyncio.run(
            _write_ingestion_audit(
                file_name=file_name,
                source=source,
                chunks_ingested=chunks_ingested,
                file_size_bytes=file_size_bytes,
                embed_model_used=embed_model_used,
                duration_ms=duration_ms,
                client_id=client_id,
                status=status,
                error_message=error_message,
            )
        )
        log.info(f"Ingestion audit complete for: {file_name}")
        return {"file_name": file_name, "status": status}

    except Exception as exc:
        log.error(f"Ingestion audit task failed: {exc}")
        raise self.retry(exc=exc)


async def _run_eval(
    query: str,
    answer: str,
    chunks: list[dict],
) -> tuple[float, float]:
    if not answer.strip() or not chunks:
        return 0.0, 0.0
    eval_service = EvalService()
    result = await eval_service.evaluate(
        query=query,
        chunks=chunks,
        answer=answer,
    )
    return result["faithfulness"], result["relevance"]


async def _write_audit(
    query: str,
    answer: str,
    chunks: list[dict],
    faithfulness: float,
    relevance: float,
    model_used: str,
    embed_model_used: str,
    duration_ms: float,
    client_id: str,
) -> None:
    import json
    async with get_audit_session() as session:
        await session.execute(
            text("""
                INSERT INTO audit_query_events (
                    client_id, query, answer, retrieved_chunks,
                    faithfulness_score, relevance_score,
                    model_used, embed_model_used, duration_ms, created_at
                ) VALUES (
                    :client_id, :query, :answer, :retrieved_chunks,
                    :faithfulness_score, :relevance_score,
                    :model_used, :embed_model_used, :duration_ms, :created_at
                )
            """),
            {
                "client_id": client_id,
                "query": query,
                "answer": answer,
                "retrieved_chunks": json.dumps(chunks),
                "faithfulness_score": faithfulness,
                "relevance_score": relevance,
                "model_used": model_used,
                "embed_model_used": embed_model_used,
                "duration_ms": duration_ms,
                "created_at": datetime.now(timezone.utc),
            },
        )
        await session.commit()


async def _write_ingestion_audit(
    file_name: str,
    source: str,
    chunks_ingested: int,
    file_size_bytes: int,
    embed_model_used: str,
    duration_ms: float,
    client_id: str,
    status: str,
    error_message: str = None,
) -> None:
    async with get_audit_session() as session:
        await session.execute(
            text("""
                INSERT INTO audit_ingestion_events (
                    client_id, file_name, source, chunks_ingested,
                    file_size_bytes, embed_model_used, duration_ms,
                    status, error_message, created_at
                ) VALUES (
                    :client_id, :file_name, :source, :chunks_ingested,
                    :file_size_bytes, :embed_model_used, :duration_ms,
                    :status, :error_message, :created_at
                )
            """),
            {
                "client_id": client_id,
                "file_name": file_name,
                "source": source,
                "chunks_ingested": chunks_ingested,
                "file_size_bytes": file_size_bytes,
                "embed_model_used": embed_model_used,
                "duration_ms": duration_ms,
                "status": status,
                "error_message": error_message,
                "created_at": datetime.now(timezone.utc),
            },
        )
        await session.commit()