import asyncio

from qdrant_client import AsyncQdrantClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.ingestion.embedder import Embedder
from app.features.retrieval.hybrid import SearchResult, reciprocal_rank_fusion


class RetrievalService:
    def __init__(self, db: AsyncSession, qdrant: AsyncQdrantClient):
        self.db = db
        self.qdrant = qdrant

    async def search(
        self,
        query: str,
        top_n: int = 5,
    ) -> list[dict]:
        # 1. Validate query
        if not query.strip():
            raise ValueError("Query cannot be empty")

        # 2. Embed the query
        embedder = Embedder()
        query_vector = await embedder.embed_text(query)

        # 3. Run Qdrant and Postgres searches in parallel
        qdrant_task = self._search_qdrant(query_vector, limit=10)
        postgres_task = self._search_postgres(query, limit=10)
        qdrant_results, postgres_results = await asyncio.gather(
            qdrant_task, postgres_task
        )

        # 4. Fuse results with RRF
        fused = reciprocal_rank_fusion(
            qdrant_results,
            postgres_results,
            top_n=top_n,
        )

        if not fused:
            return []

        # 5. Fetch full chunk text from Postgres
        chunks = await self._fetch_chunks(fused)
        return chunks

    async def _search_qdrant(
        self,
        query_vector: list[float],
        limit: int,
    ) -> list[SearchResult]:
        """
        Dense semantic search in Qdrant.
        Returns top N most similar vectors to the query.
        """
        hits = await self.qdrant.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=limit,
        )
        return [
            SearchResult(
                qdrant_id=str(hit.id),
                score=hit.score,
                source="qdrant",
                metadata=hit.payload or {},
            )
            for hit in hits
        ]

    async def _search_postgres(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        """
        Sparse BM25 full-text search in Postgres.
        Uses tsvector + tsquery for keyword matching.
        ts_rank scores how well the document matches the query.
        """
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
        """
        After fusion we only have qdrant_ids and scores.
        Fetch the actual chunk text and metadata from Postgres.
        """
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

        # Preserve RRF order
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