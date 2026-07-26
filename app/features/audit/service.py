from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_query_events(
        self,
        client_id: str = None,
        max_faithfulness: float = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """
        Fetch query audit events with optional filters.
        Auditors use this to investigate incidents.
        """
        conditions = ["1=1"]
        params = {"limit": limit, "offset": offset}

        if client_id:
            conditions.append("client_id = :client_id")
            params["client_id"] = client_id

        if max_faithfulness is not None:
            conditions.append("faithfulness_score <= :max_faithfulness")
            params["max_faithfulness"] = max_faithfulness

        where = " AND ".join(conditions)

        result = await self.db.execute(
            text(f"""
                SELECT
                    id, client_id, query, answer,
                    faithfulness_score, relevance_score,
                    model_used, embed_model_used,
                    duration_ms, created_at
                FROM audit_query_events
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        rows = result.fetchall()
        return [
            {
                "id": row.id,
                "client_id": row.client_id,
                "query": row.query,
                "answer": row.answer,
                "faithfulness_score": row.faithfulness_score,
                "relevance_score": row.relevance_score,
                "model_used": row.model_used,
                "embed_model_used": row.embed_model_used,
                "duration_ms": row.duration_ms,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def get_ingestion_events(
        self,
        client_id: str = None,
        status: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """
        Fetch ingestion audit events with optional filters.
        """
        conditions = ["1=1"]
        params = {"limit": limit, "offset": offset}

        if client_id:
            conditions.append("client_id = :client_id")
            params["client_id"] = client_id

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where = " AND ".join(conditions)

        result = await self.db.execute(
            text(f"""
                SELECT
                    id, client_id, file_name, source,
                    chunks_ingested, file_size_bytes,
                    embed_model_used, duration_ms,
                    status, error_message, created_at
                FROM audit_ingestion_events
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        rows = result.fetchall()
        return [
            {
                "id": row.id,
                "client_id": row.client_id,
                "file_name": row.file_name,
                "source": row.source,
                "chunks_ingested": row.chunks_ingested,
                "file_size_bytes": row.file_size_bytes,
                "embed_model_used": row.embed_model_used,
                "duration_ms": row.duration_ms,
                "status": row.status,
                "error_message": row.error_message,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]