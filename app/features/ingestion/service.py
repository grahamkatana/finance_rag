import uuid

from pypdf import PdfReader
from io import BytesIO
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.ingestion.chunker import Chunker
from app.features.ingestion.embedder import Embedder


def extract_text(file_bytes: bytes) -> str:
    """
    Extract raw text from PDF bytes using pypdf.
    """
    reader = PdfReader(BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages.append(page_text)
    return "\n\n".join(pages)


class IngestionService:
    def __init__(self, db: AsyncSession, qdrant: AsyncQdrantClient):
        self.db = db
        self.qdrant = qdrant

    async def ingest(
        self,
        file_bytes: bytes,
        file_name: str,
        source: str,
    ) -> dict:
        # 1. Extract text from PDF
        raw_text = extract_text(file_bytes)
        if not raw_text.strip():
            raise ValueError("No text could be extracted from this PDF")

        # 2. Chunk the text
        chunker = Chunker()
        chunks = chunker.chunk(raw_text)
        if not chunks:
            raise ValueError("No text could be extracted from this PDF")

        # 3. Embed all chunks in one batch call
        embedder = Embedder()
        texts = [chunk.text for chunk in chunks]
        vectors = await embedder.embed_batch(texts)

        # 4. Build Qdrant points
        points = []
        qdrant_ids = []

        for chunk, vector in zip(chunks, vectors):
            qdrant_id = str(uuid.uuid4())
            qdrant_ids.append(qdrant_id)

            points.append(PointStruct(
                id=qdrant_id,
                vector=vector,
                payload={
                    "file_name": file_name,
                    "chunk_index": chunk.chunk_index,
                    "source": source,
                },
            ))

        # 5. Upsert vectors into Qdrant
        await self.qdrant.upsert(
            collection_name=settings.qdrant_collection,
            points=points,
        )

        # 6. Store metadata + tsvector in Postgres
        for chunk, qdrant_id in zip(chunks, qdrant_ids):
            await self.db.execute(
                text("""
                    INSERT INTO documents (
                        file_name,
                        file_type,
                        source,
                        chunk_text,
                        chunk_index,
                        qdrant_id,
                        fts_vector
                    ) VALUES (
                        :file_name,
                        :file_type,
                        :source,
                        :chunk_text,
                        :chunk_index,
                        :qdrant_id,
                        to_tsvector('english', :chunk_text)
                    )
                """),
                {
                    "file_name": file_name,
                    "file_type": "pdf",
                    "source": source,
                    "chunk_text": chunk.text,
                    "chunk_index": chunk.chunk_index,
                    "qdrant_id": qdrant_id,
                },
            )

        await self.db.commit()

        return {
            "file_name": file_name,
            "chunks_ingested": len(chunks),
            "source": source,
        }