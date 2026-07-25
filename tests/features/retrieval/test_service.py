import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.features.retrieval.service import RetrievalService
from app.features.retrieval.hybrid import SearchResult


@pytest.fixture
def mock_db():
    session = AsyncMock()
    return session


@pytest.fixture
def mock_qdrant():
    client = AsyncMock()
    return client


@pytest.fixture
def service(mock_db, mock_qdrant):
    return RetrievalService(db=mock_db, qdrant=mock_qdrant)


@pytest.fixture
def mock_qdrant_hits():
    """Simulated Qdrant search hits"""
    hit1 = MagicMock()
    hit1.id = "uuid-a"
    hit1.score = 0.95
    hit1.payload = {
        "file_name": "apple_10k.pdf",
        "chunk_index": 1,
        "source": "sec.gov",
    }

    hit2 = MagicMock()
    hit2.id = "uuid-b"
    hit2.score = 0.87
    hit2.payload = {
        "file_name": "apple_10k.pdf",
        "chunk_index": 2,
        "source": "sec.gov",
    }
    return [hit1, hit2]


@pytest.fixture
def mock_pg_rows():
    """Simulated Postgres BM25 rows"""
    row1 = MagicMock()
    row1.qdrant_id = "uuid-b"
    row1.rank = 0.91

    row2 = MagicMock()
    row2.qdrant_id = "uuid-c"
    row2.rank = 0.85
    return [row1, row2]


@pytest.fixture
def mock_chunk_rows():
    """Simulated Postgres chunk fetch results"""
    row1 = MagicMock()
    row1.qdrant_id = "uuid-a"
    row1.chunk_text = "Apple revenue grew 12% in Q3 2023."
    row1.file_name = "apple_10k.pdf"
    row1.chunk_index = 1
    row1.source = "sec.gov"

    row2 = MagicMock()
    row2.qdrant_id = "uuid-b"
    row2.chunk_text = "Net income rose to $19.9 billion."
    row2.file_name = "apple_10k.pdf"
    row2.chunk_index = 2
    row2.source = "sec.gov"
    return [row1, row2]


@pytest.mark.asyncio
async def test_search_returns_list(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Search must return a list"""
    with patch("app.features.retrieval.service.Embedder") as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        service.qdrant.search.return_value = mock_qdrant_hits

        mock_execute = AsyncMock()
        mock_result_pg = MagicMock()
        mock_result_pg.fetchall.return_value = mock_pg_rows
        mock_result_chunks = MagicMock()
        mock_result_chunks.fetchall.return_value = mock_chunk_rows
        mock_execute.side_effect = [mock_result_pg, mock_result_chunks]
        service.db.execute = mock_execute

        results = await service.search(query="Apple revenue Q3")
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_returns_correct_fields(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Each result must have chunk_text, file_name, score, source"""
    with patch("app.features.retrieval.service.Embedder") as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        service.qdrant.search.return_value = mock_qdrant_hits

        mock_execute = AsyncMock()
        mock_result_pg = MagicMock()
        mock_result_pg.fetchall.return_value = mock_pg_rows
        mock_result_chunks = MagicMock()
        mock_result_chunks.fetchall.return_value = mock_chunk_rows
        mock_execute.side_effect = [mock_result_pg, mock_result_chunks]
        service.db.execute = mock_execute

        results = await service.search(query="Apple revenue Q3")
        for result in results:
            assert "chunk_text" in result
            assert "file_name" in result
            assert "score" in result
            assert "source" in result


@pytest.mark.asyncio
async def test_search_calls_qdrant(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Qdrant search must be called with a vector"""
    with patch("app.features.retrieval.service.Embedder") as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        service.qdrant.search.return_value = mock_qdrant_hits

        mock_execute = AsyncMock()
        mock_result_pg = MagicMock()
        mock_result_pg.fetchall.return_value = mock_pg_rows
        mock_result_chunks = MagicMock()
        mock_result_chunks.fetchall.return_value = mock_chunk_rows
        mock_execute.side_effect = [mock_result_pg, mock_result_chunks]
        service.db.execute = mock_execute

        await service.search(query="Apple revenue Q3")
        assert service.qdrant.search.called


@pytest.mark.asyncio
async def test_search_calls_postgres(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Postgres execute must be called for BM25 search"""
    with patch("app.features.retrieval.service.Embedder") as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        service.qdrant.search.return_value = mock_qdrant_hits

        mock_execute = AsyncMock()
        mock_result_pg = MagicMock()
        mock_result_pg.fetchall.return_value = mock_pg_rows
        mock_result_chunks = MagicMock()
        mock_result_chunks.fetchall.return_value = mock_chunk_rows
        mock_execute.side_effect = [mock_result_pg, mock_result_chunks]
        service.db.execute = mock_execute

        await service.search(query="Apple revenue Q3")
        assert service.db.execute.called


@pytest.mark.asyncio
async def test_search_empty_query_raises(service):
    """Empty query string should raise ValueError"""
    with pytest.raises(ValueError, match="Query cannot be empty"):
        await service.search(query="")


@pytest.mark.asyncio
async def test_search_top_n_respected(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """top_n parameter must limit results returned"""
    with patch("app.features.retrieval.service.Embedder") as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        service.qdrant.search.return_value = mock_qdrant_hits

        mock_execute = AsyncMock()
        mock_result_pg = MagicMock()
        mock_result_pg.fetchall.return_value = mock_pg_rows
        mock_result_chunks = MagicMock()
        mock_result_chunks.fetchall.return_value = mock_chunk_rows
        mock_execute.side_effect = [mock_result_pg, mock_result_chunks]
        service.db.execute = mock_execute

        results = await service.search(query="Apple revenue Q3", top_n=1)
        assert len(results) <= 1