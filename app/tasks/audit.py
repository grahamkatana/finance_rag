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
    """
    Background task that:
    1. Runs faithfulness + relevance eval
    2. Writes full audit record to Postgres
    """
    try:
        log.info(f"Processing audit for query: {query[:50]}...")

        # Run async eval in sync Celery context
        faithfulness, relevance = asyncio.run(
            _run_eval(query=query, answer=answer, chunks=chunks)
        )

        # Write audit record
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
        return {
            "faithfulness": faithfulness,
            "relevance": relevance,
        }

    except Exception as exc:
        log.error(f"Audit task failed: {exc}")
        raise self.retry(exc=exc)


async def _run_eval(
    query: str,
    answer: str,
    chunks: list[dict],
) -> tuple[float, float]:
    """Run eval scoring asynchronously."""
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
    """Write audit record to Postgres."""
    import json

    async with get_audit_session() as session:
        await session.execute(
            text("""
                INSERT INTO audit_query_events (
                    client_id,
                    query,
                    answer,
                    retrieved_chunks,
                    faithfulness_score,
                    relevance_score,
                    model_used,
                    embed_model_used,
                    duration_ms,
                    created_at
                ) VALUES (
                    :client_id,
                    :query,
                    :answer,
                    :retrieved_chunks,
                    :faithfulness_score,
                    :relevance_score,
                    :model_used,
                    :embed_model_used,
                    :duration_ms,
                    :created_at
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