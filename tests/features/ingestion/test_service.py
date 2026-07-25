import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.features.ingestion.service import IngestionService


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_qdrant():
    client = AsyncMock()
    client.upsert = AsyncMock()
    return client


@pytest.fixture
def service(mock_db, mock_qdrant):
    return IngestionService(db=mock_db, qdrant=mock_qdrant)


@pytest.mark.asyncio
async def test_ingest_returns_chunk_count(service):
    """Ingestion should return how many chunks were processed"""
    pdf_bytes = b"%PDF-1.4 mock content"
    with patch("app.features.ingestion.service.extract_text") as mock_extract, \
         patch("app.features.ingestion.service.Chunker") as mock_chunker_cls, \
         patch("app.features.ingestion.service.Embedder") as mock_embedder_cls:

        mock_extract.return_value = "Apple revenue grew 12% in Q3. " * 20

        mock_chunk = MagicMock()
        mock_chunk.text = "Apple revenue grew 12% in Q3."
        mock_chunk.chunk_index = 0
        mock_chunk.char_start = 0
        mock_chunk.char_end = 29

        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = [mock_chunk, mock_chunk]
        mock_chunker_cls.return_value = mock_chunker

        mock_embedder = AsyncMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768, [0.1] * 768]
        mock_embedder_cls.return_value = mock_embedder

        result = await service.ingest(
            file_bytes=pdf_bytes,
            file_name="apple_10k.pdf",
            source="https://sec.gov/apple"
        )

        assert result["chunks_ingested"] == 2
        assert result["file_name"] == "apple_10k.pdf"


@pytest.mark.asyncio
async def test_ingest_calls_qdrant_upsert(service):
    """Qdrant upsert must be called with vectors"""
    with patch("app.features.ingestion.service.extract_text") as mock_extract, \
         patch("app.features.ingestion.service.Chunker") as mock_chunker_cls, \
         patch("app.features.ingestion.service.Embedder") as mock_embedder_cls:

        mock_extract.return_value = "Apple revenue grew 12% in Q3. " * 20

        mock_chunk = MagicMock()
        mock_chunk.text = "Apple revenue grew 12% in Q3."
        mock_chunk.chunk_index = 0
        mock_chunk.char_start = 0
        mock_chunk.char_end = 29

        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = [mock_chunk]
        mock_chunker_cls.return_value = mock_chunker

        mock_embedder = AsyncMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768]
        mock_embedder_cls.return_value = mock_embedder

        await service.ingest(
            file_bytes=b"%PDF mock",
            file_name="apple_10k.pdf",
            source="https://sec.gov/apple"
        )

        assert service.qdrant.upsert.called


@pytest.mark.asyncio
async def test_ingest_calls_db_execute(service):
    """PostgreSQL execute must be called to store chunk metadata"""
    with patch("app.features.ingestion.service.extract_text") as mock_extract, \
         patch("app.features.ingestion.service.Chunker") as mock_chunker_cls, \
         patch("app.features.ingestion.service.Embedder") as mock_embedder_cls:

        mock_extract.return_value = "Apple revenue grew 12% in Q3. " * 20

        mock_chunk = MagicMock()
        mock_chunk.text = "Apple revenue grew 12% in Q3."
        mock_chunk.chunk_index = 0
        mock_chunk.char_start = 0
        mock_chunk.char_end = 29

        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = [mock_chunk]
        mock_chunker_cls.return_value = mock_chunker

        mock_embedder = AsyncMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768]
        mock_embedder_cls.return_value = mock_embedder

        await service.ingest(
            file_bytes=b"%PDF mock",
            file_name="apple_10k.pdf",
            source="https://sec.gov/apple"
        )

        assert service.db.execute.called


@pytest.mark.asyncio
async def test_ingest_empty_pdf_raises(service):
    """Empty PDF text should raise a ValueError"""
    with patch("app.features.ingestion.service.extract_text") as mock_extract, \
         patch("app.features.ingestion.service.Chunker") as mock_chunker_cls, \
         patch("app.features.ingestion.service.Embedder") as mock_embedder_cls:

        mock_extract.return_value = ""

        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = []
        mock_chunker_cls.return_value = mock_chunker

        mock_embedder = AsyncMock()
        mock_embedder_cls.return_value = mock_embedder

        with pytest.raises(ValueError, match="No text could be extracted"):
            await service.ingest(
                file_bytes=b"%PDF mock",
                file_name="empty.pdf",
                source="local"
            )