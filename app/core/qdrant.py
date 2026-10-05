from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    VectorParams,
)

from app.core.config import settings

# 1. Client
client = AsyncQdrantClient(
    host=settings.qdrant_host,
    port=settings.qdrant_port,
    api_key=settings.qdrant_api_key or None,
    https=False,  # shared Qdrant is plain HTTP internally; api_key alone would force HTTPS
)


async def init_qdrant() -> None:
    """
    Called once at app startup.
    Creates the collection if it doesn't exist.
    """
    existing = await client.get_collections()
    collection_names = [c.name for c in existing.collections]

    if settings.qdrant_collection not in collection_names:
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_size,
                distance=Distance.COSINE,
            ),
            # int8 scalar quantization, pinned in RAM. The shared Qdrant pod is
            # memory-capped; unquantized float vectors get paged out and every
            # search re-reads them from disk (this took books_rag searches from
            # ~50 ms to 20-30 s -- see books_rag/QDRANT_QUANTIZATION.md). 4x
            # smaller vectors stay resident; recall stays >99% for RAG.
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(type=ScalarType.INT8, always_ram=True)
            ),
        )
        print(f"Created Qdrant collection: {settings.qdrant_collection}")
    else:
        print(f"Qdrant collection already exists: {settings.qdrant_collection}")


async def get_qdrant() -> AsyncQdrantClient:
    """
    FastAPI dependency — same pattern as get_db.
    """
    return client