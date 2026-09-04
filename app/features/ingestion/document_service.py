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

    async def file_exists(self, file_name: str, owner_id: int) -> bool:
        """
        Check if a file has already been ingested by this owner.
        Used to prevent duplicate ingestion.
        """
        result = await self.db.execute(
            text("""
                SELECT COUNT(*) as count
                FROM documents
                WHERE file_name = :file_name AND owner_id = :owner_id
            """),
            {"file_name": file_name, "owner_id": owner_id},
        )
        row = result.fetchone()
        return row.count > 0

    async def _visible_file_names(self, owner_id: int, is_admin: bool) -> list[str] | None:
        """
        Return the list of file_names the user can access, or None for admin
        (admin sees everything).
        """
        if is_admin:
            return None

        owned = await self.db.execute(
            text("""
                SELECT DISTINCT file_name FROM documents
                WHERE owner_id = :owner_id
            """),
            {"owner_id": owner_id},
        )
        owned_names = [row.file_name for row in owned.fetchall()]

        shared = await self.db.execute(
            text("""
                SELECT DISTINCT file_name FROM document_shares
                WHERE granted_to_user_id = :owner_id
            """),
            {"owner_id": owner_id},
        )
        shared_names = [row.file_name for row in shared.fetchall()]

        return list(set(owned_names + shared_names))

    async def list_documents(self, owner_id: int, is_admin: bool) -> list[dict]:
        """
        Return a summary of documents visible to the user.
        Non-admins see owned + shared documents; admins see everything.
        """
        if is_admin:
            where = ""
            params = {}
        else:
            visible = await self._visible_file_names(owner_id, is_admin)
            if not visible:
                return []
            where = "WHERE file_name = ANY(:files)"
            params = {"files": visible}

        result = await self.db.execute(
            text(f"""
                SELECT
                    file_name,
                    source,
                    COUNT(*) as chunk_count,
                    MIN(created_at) as created_at
                FROM documents
                {where}
                GROUP BY file_name, source
                ORDER BY MIN(created_at) DESC
            """),
            params,
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

    async def _get_qdrant_ids_for_file(
        self,
        file_name: str,
        owner_id: int | None = None,
        is_admin: bool = False,
    ) -> list[str]:
        where = "file_name = :file_name"
        params = {"file_name": file_name}
        if not is_admin:
            where += " AND owner_id = :owner_id"
            params["owner_id"] = owner_id
        result = await self.db.execute(
            text(f"SELECT qdrant_id FROM documents WHERE {where}"),
            params,
        )
        rows = result.fetchall()
        return [row.qdrant_id for row in rows]

    async def delete_document(
        self,
        file_name: str,
        owner_id: int,
        is_admin: bool = False,
    ) -> dict:
        """
        Delete all chunks for a document from both Postgres and Qdrant.
        Non-admins can only delete documents they own.
        """
        self.log.info(f"Deleting document: {file_name} (requester={owner_id}, admin={is_admin})")

        qdrant_ids = await self._get_qdrant_ids_for_file(
            file_name, owner_id, is_admin
        )
        if not qdrant_ids:
            return {"file_name": file_name, "chunks_deleted": 0}

        # 2. Delete from Qdrant
        await self.qdrant.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qdrant_ids,
        )
        self.log.info(f"Deleted {len(qdrant_ids)} vectors from Qdrant")

        # 3. Delete from Postgres
        if is_admin:
            await self.db.execute(
                text("DELETE FROM documents WHERE file_name = :file_name"),
                {"file_name": file_name},
            )
            await self.db.execute(
                text("DELETE FROM document_shares WHERE file_name = :file_name"),
                {"file_name": file_name},
            )
        else:
            await self.db.execute(
                text(
                    "DELETE FROM documents "
                    "WHERE file_name = :file_name AND owner_id = :owner_id"
                ),
                {"file_name": file_name, "owner_id": owner_id},
            )
            await self.db.execute(
                text(
                    "DELETE FROM document_shares "
                    "WHERE file_name = :file_name AND owner_id = :owner_id"
                ),
                {"file_name": file_name, "owner_id": owner_id},
            )
        await self.db.commit()
        self.log.info(f"Deleted {len(qdrant_ids)} chunks from Postgres")

        return {
            "file_name": file_name,
            "chunks_deleted": len(qdrant_ids),
        }

    # ---- Sharing ----

    async def is_owner(self, file_name: str, owner_id: int) -> bool:
        """Whether the user owns any chunk of the given file."""
        result = await self.db.execute(
            text("""
                SELECT COUNT(*) as count FROM documents
                WHERE file_name = :file_name AND owner_id = :owner_id
            """),
            {"file_name": file_name, "owner_id": owner_id},
        )
        return result.fetchone().count > 0

    async def share_file(self, file_name: str, owner_id: int, granted_to_user_id: int) -> bool:
        """Share a file with another user. Returns False if owner not found."""
        if not await self.is_owner(file_name, owner_id):
            return False
        if granted_to_user_id == owner_id:
            raise ValueError("Cannot share a file with yourself")
        await self.db.execute(
            text("""
                INSERT INTO document_shares (file_name, owner_id, granted_to_user_id)
                VALUES (:file_name, :owner_id, :granted_to_user_id)
                ON CONFLICT (file_name, granted_to_user_id) DO NOTHING
            """),
            {
                "file_name": file_name,
                "owner_id": owner_id,
                "granted_to_user_id": granted_to_user_id,
            },
        )
        await self.db.commit()
        return True

    async def unshare_file(self, file_name: str, owner_id: int, granted_to_user_id: int) -> int:
        """Revoke a share. Returns number of rows removed."""
        result = await self.db.execute(
            text("""
                DELETE FROM document_shares
                WHERE file_name = :file_name
                  AND owner_id = :owner_id
                  AND granted_to_user_id = :granted_to_user_id
            """),
            {
                "file_name": file_name,
                "owner_id": owner_id,
                "granted_to_user_id": granted_to_user_id,
            },
        )
        await self.db.commit()
        return result.rowcount

    async def list_shares(self, file_name: str, owner_id: int) -> list[dict]:
        """List who a file is shared with. Owner (or admin) only."""
        result = await self.db.execute(
            text("""
                SELECT granted_to_user_id, created_at
                FROM document_shares
                WHERE file_name = :file_name AND owner_id = :owner_id
                ORDER BY created_at DESC
            """),
            {"file_name": file_name, "owner_id": owner_id},
        )
        rows = result.fetchall()
        return [
            {
                "granted_to_user_id": row.granted_to_user_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
