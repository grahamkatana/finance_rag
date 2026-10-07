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
            source="https://sec.gov/apple",
            owner_id=1,
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
            source="https://sec.gov/apple",
            owner_id=1,
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
            source="https://sec.gov/apple",
            owner_id=1,
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
                source="local",
                owner_id=1,
            )


@pytest.mark.asyncio
async def test_ingest_stores_owner_id_in_qdrant_payload(service):
    """Qdrant points must carry the document owner_id for scoped search."""
    with patch("app.features.ingestion.service.extract_text") as mock_extract, \
         patch("app.features.ingestion.service.Chunker") as mock_chunker_cls, \
         patch("app.features.ingestion.service.Embedder") as mock_embedder_cls:

        mock_extract.return_value = "Apple revenue grew 12% in Q3. " * 20

        mock_chunk = MagicMock()
        mock_chunk.text = "Apple revenue grew 12% in Q3."
        mock_chunk.chunk_index = 0
        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = [mock_chunk]
        mock_chunker_cls.return_value = mock_chunker

        mock_embedder = AsyncMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768]
        mock_embedder_cls.return_value = mock_embedder

        await service.ingest(
            file_bytes=b"%PDF mock",
            file_name="apple_10k.pdf",
            source="sec.gov",
            owner_id=7,
        )

        _, kwargs = service.qdrant.upsert.call_args
        points = kwargs["points"]
        assert points[0].payload["owner_id"] == 7

@pytest.mark.asyncio
async def test_extraction_runs_off_the_event_loop_thread(service):
    """PDF extraction is CPU-bound; on the loop thread it blocks /health and gets the pod killed"""
    import threading

    loop_thread = threading.current_thread()
    seen = {}

    def fake_extract(_file_bytes):
        seen["extract"] = threading.current_thread()
        return "Apple revenue grew 12% in Q3. " * 20

    mock_chunk = MagicMock()
    mock_chunk.text = "Apple revenue grew 12% in Q3."
    mock_chunk.chunk_index = 0

    def fake_chunk(_text):
        seen["chunk"] = threading.current_thread()
        return [mock_chunk]

    with patch("app.features.ingestion.service.extract_text", fake_extract), \
         patch("app.features.ingestion.service.Chunker") as mock_chunker_cls, \
         patch("app.features.ingestion.service.Embedder") as mock_embedder_cls:

        mock_chunker_cls.return_value.chunk = fake_chunk
        mock_embedder = AsyncMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768]
        mock_embedder_cls.return_value = mock_embedder

        await service.ingest(
            file_bytes=b"%PDF-1.4 mock",
            file_name="apple_10k.pdf",
            source="https://sec.gov/apple",
            owner_id=1,
        )

    assert seen["extract"] is not loop_thread
    assert seen["chunk"] is not loop_thread


@pytest.mark.asyncio
async def test_large_upserts_are_sent_in_batches(service, mock_qdrant):
    """Qdrant rejects a single request over 32 MB, so a big PDF must be upserted in batches"""
    n = 450
    mock_chunk = MagicMock()
    mock_chunk.text = "Apple revenue grew 12% in Q3."
    mock_chunk.chunk_index = 0

    with patch("app.features.ingestion.service.extract_text", return_value="x" * 100), \
         patch("app.features.ingestion.service.Chunker") as mock_chunker_cls, \
         patch("app.features.ingestion.service.Embedder") as mock_embedder_cls:
        mock_chunker_cls.return_value.chunk.return_value = [mock_chunk] * n
        mock_embedder = AsyncMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 8] * n
        mock_embedder_cls.return_value = mock_embedder

        await service.ingest(b"%PDF", "big.pdf", "src", 1)

    sizes = [len(c.kwargs["points"]) for c in mock_qdrant.upsert.call_args_list]
    assert sum(sizes) == n
    assert len(sizes) == 3
    assert max(sizes) <= 200


@pytest.mark.asyncio
async def test_failed_upsert_removes_vectors_already_written(service, mock_qdrant):
    """A mid-way failure must not leave orphan vectors that have no Postgres rows"""
    mock_chunk = MagicMock()
    mock_chunk.text = "Apple revenue grew 12% in Q3."
    mock_chunk.chunk_index = 0
    mock_qdrant.upsert.side_effect = [None, RuntimeError("qdrant down")]

    with patch("app.features.ingestion.service.extract_text", return_value="x" * 100), \
         patch("app.features.ingestion.service.Chunker") as mock_chunker_cls, \
         patch("app.features.ingestion.service.Embedder") as mock_embedder_cls:
        mock_chunker_cls.return_value.chunk.return_value = [mock_chunk] * 300
        mock_embedder = AsyncMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 8] * 300
        mock_embedder_cls.return_value = mock_embedder

        with pytest.raises(RuntimeError):
            await service.ingest(b"%PDF", "big.pdf", "src", 1)

    mock_qdrant.delete.assert_awaited_once()
    assert len(mock_qdrant.delete.call_args.kwargs["points_selector"].points) == 300
