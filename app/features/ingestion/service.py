import uuid
from io import BytesIO
from typing import AsyncGenerator

from pypdf import PdfReader
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.features.ingestion.chunker import Chunker
from app.features.ingestion.embedder import Embedder


def extract_text(file_bytes: bytes) -> str:
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
        self.log = logger.getChild("ingestion")

    async def ingest(
        self,
        file_bytes: bytes,
        file_name: str,
        source: str,
        owner_id: int,
    ) -> dict:
        async for event in self.ingest_with_progress(
            file_bytes=file_bytes,
            file_name=file_name,
            source=source,
            owner_id=owner_id,
        ):
            if event["status"] == "done":
                return {
                    "file_name": event["file_name"],
                    "chunks_ingested": event["chunks_ingested"],
                    "source": event["source"],
                    "owner_id": owner_id,
                }
        raise ValueError("Ingestion failed")

    async def ingest_with_progress(
        self,
        file_bytes: bytes,
        file_name: str,
        source: str,
        owner_id: int,
    ) -> AsyncGenerator[dict, None]:
        self.log.info(f"Starting ingestion: {file_name}")
        yield {"status": "extracting", "message": f"Extracting text from {file_name}..."}

        raw_text = extract_text(file_bytes)
        if not raw_text.strip():
            self.log.error(f"No text extracted from {file_name}")
            raise ValueError("No text could be extracted from this PDF")

        self.log.info(f"Extracted {len(raw_text)} characters from {file_name}")
        yield {"status": "chunking", "message": f"Extracted {len(raw_text)} characters, chunking..."}

        chunker = Chunker()
        chunks = chunker.chunk(raw_text)
        if not chunks:
            raise ValueError("No text could be extracted from this PDF")

        self.log.info(f"Created {len(chunks)} chunks from {file_name}")
        yield {"status": "embedding", "message": f"Embedding {len(chunks)} chunks...", "total": len(chunks)}

        embedder = Embedder()
        texts = [chunk.text for chunk in chunks]
        vectors = await embedder.embed_batch(texts)

        self.log.info(f"Embedding complete for {file_name}")
        yield {"status": "storing", "message": f"Storing {len(chunks)} vectors in Qdrant..."}

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
                    "owner_id": owner_id,
                },
            ))

        await self.qdrant.upsert(
            collection_name=settings.qdrant_collection,
            points=points,
        )

        self.log.info("Qdrant upsert complete")
        yield {"status": "saving", "message": "Saving metadata to Postgres..."}

        for i, (chunk, qdrant_id) in enumerate(zip(chunks, qdrant_ids)):
            if i % 10 == 0:
                yield {
                    "status": "saving",
                    "message": f"Writing chunks to Postgres...",
                    "progress": i,
                    "total": len(chunks),
                }
            await self.db.execute(
                text("""
                    INSERT INTO documents (
                        file_name, file_type, source,
                        chunk_text, chunk_index, qdrant_id, owner_id, fts_vector
                    ) VALUES (
                        :file_name, :file_type, :source,
                        :chunk_text, :chunk_index, :qdrant_id, :owner_id,
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
                    "owner_id": owner_id,
                },
            )

        await self.db.commit()
        self.log.info(f"Ingestion complete: {file_name} — {len(chunks)} chunks stored")

        yield {
            "status": "done",
            "message": f"Ingestion complete",
            "file_name": file_name,
            "chunks_ingested": len(chunks),
            "source": source,
        }