"""
Re-embed every stored chunk into the configured Qdrant collection.

Run after changing the embedding model (EMBED_PROVIDER / EMBED_MODEL /
EMBEDDING_SIZE) and pointing QDRANT_COLLECTION at a new collection name:

    uv run python -m app.reembed

Vectors from different models are not comparable, so the old collection
can't be reused -- but the chunk text is already in Postgres, so nothing has
to be re-uploaded or re-chunked. Each chunk keeps its existing point id and
payload, so ownership, sharing and the Postgres `qdrant_id` links are all
unchanged. Safe to re-run: points are upserted by id.
"""

import asyncio

from qdrant_client.models import PointStruct
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.core.qdrant import client, init_qdrant
from app.features.ingestion.embedder import Embedder

log = logger.getChild("reembed")

BATCH_SIZE = 64


async def reembed_all(db, qdrant, embedder, batch_size: int = BATCH_SIZE) -> int:
    """Embeds every row of `documents` and upserts it under its existing point id. Returns the count."""
    result = await db.execute(
        text("""
            SELECT qdrant_id, file_name, chunk_index, source, owner_id, chunk_text
            FROM documents
            ORDER BY id
        """)
    )
    rows = result.fetchall()

    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        vectors = await embedder.embed_batch([row.chunk_text for row in batch])
        await qdrant.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(
                    id=row.qdrant_id,
                    vector=vector,
                    # same payload ingestion writes (features/ingestion/service.py)
                    payload={
                        "file_name": row.file_name,
                        "chunk_index": row.chunk_index,
                        "source": row.source,
                        "owner_id": row.owner_id,
                    },
                )
                for row, vector in zip(batch, vectors)
            ],
        )
        log.info(f"Re-embedded {start + len(batch)}/{len(rows)} chunks")

    return len(rows)


async def main() -> None:
    await init_qdrant()  # creates the collection (quantized) if it doesn't exist yet
    async with AsyncSessionLocal() as db:
        count = await reembed_all(db, client, Embedder())
    info = await client.get_collection(settings.qdrant_collection)
    print(
        f"Re-embedded {count} chunks into '{settings.qdrant_collection}' "
        f"with {settings.embed_provider}/{settings.embed_model}; "
        f"collection now holds {info.points_count} points, "
        f"quantization={info.config.quantization_config is not None}"
    )


if __name__ == "__main__":
    asyncio.run(main())
