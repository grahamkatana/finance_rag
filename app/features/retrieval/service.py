import time

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.features.ingestion.embedder import Embedder
from app.features.retrieval.hybrid import SearchResult, reciprocal_rank_fusion


class RetrievalService:
    def __init__(self, db: AsyncSession, qdrant: AsyncQdrantClient):
        self.db = db
        self.qdrant = qdrant
        self.log = logger.getChild("retrieval")

    async def search(
        self,
        query: str,
        top_n: int = 5,
        owner_id: int | None = None,
        is_admin: bool = False,
    ) -> list[dict]:
        if not query.strip():
            raise ValueError("Query cannot be empty")

        t0 = time.perf_counter()
        embedder = Embedder()
        query_vector = await embedder.embed_text(query)
        self.log.info(f"Query embedding took {time.perf_counter() - t0:.2f}s")

        shared_files = await self._shared_file_names(owner_id) if not is_admin else []
        user_filter = self._build_user_filter(owner_id, shared_files, is_admin)

        t1 = time.perf_counter()
        qdrant_results = await self._search_qdrant(
            query_vector, limit=10, user_filter=user_filter
        )
        self.log.info(f"Qdrant search took {time.perf_counter() - t1:.2f}s")

        t2 = time.perf_counter()
        postgres_results = await self._search_postgres(
            query, limit=10, owner_id=owner_id, is_admin=is_admin
        )
        self.log.info(f"Postgres search took {time.perf_counter() - t2:.2f}s")

        fused = reciprocal_rank_fusion(
            qdrant_results,
            postgres_results,
            top_n=top_n,
        )

        if not fused:
            return []

        t3 = time.perf_counter()
        chunks = await self._fetch_chunks(fused, owner_id=owner_id, is_admin=is_admin)
        self.log.info(f"Chunk fetch took {time.perf_counter() - t3:.2f}s")
        self.log.info(f"Total retrieval took {time.perf_counter() - t0:.2f}s")

        return chunks

    async def _shared_file_names(self, owner_id: int) -> list[str]:
        result = await self.db.execute(
            text("""
                SELECT DISTINCT file_name FROM document_shares
                WHERE granted_to_user_id = :uid
            """),
            {"uid": owner_id},
        )
        return [row.file_name for row in result.fetchall()]

    def _build_user_filter(
        self,
        owner_id: int | None,
        shared_files: list[str],
        is_admin: bool,
    ) -> Filter | None:
        """Build a Qdrant Filter so results are limited to owned + shared files."""
        if is_admin:
            return None
        if owner_id is None:
            return None

        conditions = [
            FieldCondition(key="owner_id", match=MatchValue(value=owner_id))
        ]
        if shared_files:
            conditions.append(
                FieldCondition(
                    key="file_name",
                    match=MatchAny(any=shared_files),
                )
            )

        if len(conditions) == 1:
            return Filter(must=[conditions[0]])
        return Filter(should=conditions)

    async def _search_qdrant(
        self,
        query_vector: list[float],
        limit: int,
        user_filter: Filter | None,
    ) -> list[SearchResult]:
        response = await self.qdrant.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            limit=limit,
            query_filter=user_filter,
        )
        return [
            SearchResult(
                qdrant_id=str(point.id),
                score=point.score,
                source="qdrant",
                metadata=point.payload or {},
            )
            for point in response.points
        ]

    async def _search_postgres(
        self,
        query: str,
        limit: int,
        owner_id: int | None,
        is_admin: bool,
    ) -> list[SearchResult]:
        if is_admin:
            where = ""
            params = {"query": query, "limit": limit}
        else:
            where = """
                AND (
                    d.owner_id = :owner_id
                    OR d.file_name IN (
                        SELECT file_name FROM document_shares
                        WHERE granted_to_user_id = :owner_id
                    )
                )
            """
            params = {"query": query, "limit": limit, "owner_id": owner_id}
        result = await self.db.execute(
            text(f"""
                SELECT
                    d.qdrant_id,
                    ts_rank(d.fts_vector, plainto_tsquery('english', :query)) AS rank
                FROM documents d
                WHERE d.fts_vector @@ plainto_tsquery('english', :query)
                {where}
                ORDER BY rank DESC
                LIMIT :limit
            """),
            params,
        )
        rows = result.fetchall()
        return [
            SearchResult(
                qdrant_id=row.qdrant_id,
                score=float(row.rank),
                source="postgres",
            )
            for row in rows
        ]

    async def _fetch_chunks(
        self,
        fused: list[SearchResult],
        owner_id: int | None,
        is_admin: bool,
    ) -> list[dict]:
        qdrant_ids = [r.qdrant_id for r in fused]
        score_map = {r.qdrant_id: r.score for r in fused}

        if is_admin:
            where = ""
            params = {"ids": qdrant_ids}
        else:
            where = """
                AND (
                    owner_id = :owner_id
                    OR file_name IN (
                        SELECT file_name FROM document_shares
                        WHERE granted_to_user_id = :owner_id
                    )
                )
            """
            params = {"ids": qdrant_ids, "owner_id": owner_id}

        result = await self.db.execute(
            text(f"""
                SELECT
                    qdrant_id,
                    chunk_text,
                    file_name,
                    chunk_index,
                    source
                FROM documents
                WHERE qdrant_id = ANY(:ids)
                {where}
            """),
            params,
        )
        rows = result.fetchall()

        row_map = {row.qdrant_id: row for row in rows}
        chunks = []
        for qdrant_id in qdrant_ids:
            if qdrant_id not in row_map:
                continue
            row = row_map[qdrant_id]
            chunks.append({
                "chunk_text": row.chunk_text,
                "file_name": row.file_name,
                "chunk_index": row.chunk_index,
                "source": row.source,
                "score": score_map[qdrant_id],
            })

        return chunks