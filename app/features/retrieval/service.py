import time

from qdrant_client import AsyncQdrantClient
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
    ) -> list[dict]:
        if not query.strip():
            raise ValueError("Query cannot be empty")

        t0 = time.perf_counter()
        embedder = Embedder()
        query_vector = await embedder.embed_text(query)
        self.log.info(f"Query embedding took {time.perf_counter() - t0:.2f}s")

        t1 = time.perf_counter()
        qdrant_results = await self._search_qdrant(query_vector, limit=10)
        self.log.info(f"Qdrant search took {time.perf_counter() - t1:.2f}s")

        t2 = time.perf_counter()
        postgres_results = await self._search_postgres(query, limit=10)
        self.log.info(f"Postgres search took {time.perf_counter() - t2:.2f}s")

        fused = reciprocal_rank_fusion(
            qdrant_results,
            postgres_results,
            top_n=top_n,
        )

        if not fused:
            return []

        t3 = time.perf_counter()
        chunks = await self._fetch_chunks(fused)
        self.log.info(f"Chunk fetch took {time.perf_counter() - t3:.2f}s")
        self.log.info(f"Total retrieval took {time.perf_counter() - t0:.2f}s")

        return chunks

    async def _search_qdrant(
        self,
        query_vector: list[float],
        limit: int,
    ) -> list[SearchResult]:
        response = await self.qdrant.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            limit=limit,
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
    ) -> list[SearchResult]:
        result = await self.db.execute(
            text("""
                SELECT
                    qdrant_id,
                    ts_rank(fts_vector, plainto_tsquery('english', :query)) AS rank
                FROM documents
                WHERE fts_vector @@ plainto_tsquery('english', :query)
                ORDER BY rank DESC
                LIMIT :limit
            """),
            {"query": query, "limit": limit},
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
    ) -> list[dict]:
        qdrant_ids = [r.qdrant_id for r in fused]
        score_map = {r.qdrant_id: r.score for r in fused}

        result = await self.db.execute(
            text("""
                SELECT
                    qdrant_id,
                    chunk_text,
                    file_name,
                    chunk_index,
                    source
                FROM documents
                WHERE qdrant_id = ANY(:ids)
            """),
            {"ids": qdrant_ids},
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