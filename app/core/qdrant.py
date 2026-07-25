from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings

# 1. Client
client = AsyncQdrantClient(
    host=settings.qdrant_host,
    port=settings.qdrant_port,
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
        )
        print(f"Created Qdrant collection: {settings.qdrant_collection}")
    else:
        print(f"Qdrant collection already exists: {settings.qdrant_collection}")


async def get_qdrant() -> AsyncQdrantClient:
    """
    FastAPI dependency — same pattern as get_db.
    """
    return client