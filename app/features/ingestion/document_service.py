from qdrant_client import AsyncQdrantClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger


class DocumentService:
    def __init__(self, db: AsyncSession, qdrant: AsyncQdrantClient):
        self.db = db
        self.qdrant = qdrant
        self.log = logger.getChild("document_service")

    async def file_exists(self, file_name: str) -> bool:
        """
        Check if a file has already been ingested.
        Used to prevent duplicate ingestion.
        """
        result = await self.db.execute(
            text("""
                SELECT COUNT(*) as count
                FROM documents
                WHERE file_name = :file_name
            """),
            {"file_name": file_name},
        )
        row = result.fetchone()
        return row.count > 0

    async def list_documents(self) -> list[dict]:
        """
        Return a summary of all ingested documents.
        Groups by file_name to show one entry per document.
        """
        result = await self.db.execute(
            text("""
                SELECT
                    file_name,
                    source,
                    COUNT(*) as chunk_count,
                    MIN(created_at) as created_at
                FROM documents
                GROUP BY file_name, source
                ORDER BY MIN(created_at) DESC
            """),
        )
        rows = result.fetchall()
        return [
            {
                "file_name": row.file_name,
                "source": row.source,
                "chunk_count": row.chunk_count,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    async def delete_document(self, file_name: str) -> dict:
        """
        Delete all chunks for a document from both
        Postgres and Qdrant.
        """
        self.log.info(f"Deleting document: {file_name}")

        # 1. Get all qdrant_ids for this file
        result = await self.db.execute(
            text("""
                SELECT qdrant_id FROM documents
                WHERE file_name = :file_name
            """),
            {"file_name": file_name},
        )
        rows = result.fetchall()
        qdrant_ids = [row.qdrant_id for row in rows]

        if not qdrant_ids:
            return {"file_name": file_name, "chunks_deleted": 0}

        # 2. Delete from Qdrant
        await self.qdrant.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qdrant_ids,
        )
        self.log.info(f"Deleted {len(qdrant_ids)} vectors from Qdrant")

        # 3. Delete from Postgres
        await self.db.execute(
            text("""
                DELETE FROM documents
                WHERE file_name = :file_name
            """),
            {"file_name": file_name},
        )
        await self.db.commit()
        self.log.info(f"Deleted {len(qdrant_ids)} chunks from Postgres")

        return {
            "file_name": file_name,
            "chunks_deleted": len(qdrant_ids),
        }