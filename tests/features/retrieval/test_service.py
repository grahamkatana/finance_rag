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
    """Simulated Qdrant query_points hits"""
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


def _setup_qdrant_mock(service, mock_qdrant_hits):
    """Helper to setup qdrant query_points mock"""
    mock_response = MagicMock()
    mock_response.points = mock_qdrant_hits
    service.qdrant.query_points = AsyncMock(return_value=mock_response)


def _setup_db_mock(service, mock_pg_rows, mock_chunk_rows, shared_rows=None):
    """Helper to setup db execute mock for a non-admin scoped search.

    For a non-admin there are 3 execute calls in order:
      1. shared file names
      2. postgres BM25 search
      3. chunk fetch
    """
    mock_execute = AsyncMock()
    mock_result_shared = MagicMock()
    mock_result_shared.fetchall.return_value = shared_rows or []
    mock_result_pg = MagicMock()
    mock_result_pg.fetchall.return_value = mock_pg_rows
    mock_result_chunks = MagicMock()
    mock_result_chunks.fetchall.return_value = mock_chunk_rows
    mock_execute.side_effect = [mock_result_shared, mock_result_pg, mock_result_chunks]
    service.db.execute = mock_execute


def _setup_db_mock_admin(service, mock_pg_rows, mock_chunk_rows):
    """For an admin there are 2 execute calls: postgres search, chunk fetch."""
    mock_execute = AsyncMock()
    mock_result_pg = MagicMock()
    mock_result_pg.fetchall.return_value = mock_pg_rows
    mock_result_chunks = MagicMock()
    mock_result_chunks.fetchall.return_value = mock_chunk_rows
    mock_execute.side_effect = [mock_result_pg, mock_result_chunks]
    service.db.execute = mock_execute


def _patch_embedder():
    return patch("app.features.retrieval.service.Embedder")


@pytest.mark.asyncio
async def test_search_returns_list(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Search must return a list for a scoped non-admin user"""
    with _patch_embedder() as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        _setup_qdrant_mock(service, mock_qdrant_hits)
        _setup_db_mock(service, mock_pg_rows, mock_chunk_rows)

        results = await service.search(
            query="Apple revenue Q3", owner_id=1, is_admin=False
        )
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_returns_correct_fields(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Each result must have chunk_text, file_name, score, source"""
    with _patch_embedder() as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        _setup_qdrant_mock(service, mock_qdrant_hits)
        _setup_db_mock(service, mock_pg_rows, mock_chunk_rows)

        results = await service.search(
            query="Apple revenue Q3", owner_id=1, is_admin=False
        )
        for result in results:
            assert "chunk_text" in result
            assert "file_name" in result
            assert "score" in result
            assert "source" in result


@pytest.mark.asyncio
async def test_search_calls_qdrant(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Qdrant query_points must be called with a vector"""
    with _patch_embedder() as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        _setup_qdrant_mock(service, mock_qdrant_hits)
        _setup_db_mock(service, mock_pg_rows, mock_chunk_rows)

        await service.search(query="Apple revenue Q3", owner_id=1, is_admin=False)
        assert service.qdrant.query_points.called


@pytest.mark.asyncio
async def test_search_calls_postgres(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Postgres execute must be called for BM25 search"""
    with _patch_embedder() as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        _setup_qdrant_mock(service, mock_qdrant_hits)
        _setup_db_mock(service, mock_pg_rows, mock_chunk_rows)

        await service.search(query="Apple revenue Q3", owner_id=1, is_admin=False)
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
    with _patch_embedder() as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        _setup_qdrant_mock(service, mock_qdrant_hits)
        _setup_db_mock(service, mock_pg_rows, mock_chunk_rows)

        results = await service.search(
            query="Apple revenue Q3", top_n=1, owner_id=1, is_admin=False
        )
        assert len(results) <= 1


# ---- Scoping-specific tests ----


@pytest.mark.asyncio
async def test_admin_search_skips_shared_file_query(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Admin search should not issue the shared-file lookup (2 execute calls)."""
    with _patch_embedder() as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        _setup_qdrant_mock(service, mock_qdrant_hits)
        _setup_db_mock_admin(service, mock_pg_rows, mock_chunk_rows)

        results = await service.search(
            query="Apple revenue Q3", owner_id=1, is_admin=True
        )
        assert isinstance(results, list)
        # admin -> only postgres search + chunk fetch
        assert service.db.execute.await_count == 2


@pytest.mark.asyncio
async def test_non_admin_qdrant_filter_restricts_owner(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Non-admin must pass a Qdrant filter scoped to their owner_id."""
    with _patch_embedder() as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        _setup_qdrant_mock(service, mock_qdrant_hits)
        _setup_db_mock(service, mock_pg_rows, mock_chunk_rows)

        await service.search(query="Apple revenue Q3", owner_id=42, is_admin=False)
        _, kwargs = service.qdrant.query_points.call_args
        assert kwargs.get("query_filter") is not None


@pytest.mark.asyncio
async def test_admin_qdrant_no_filter(
    service, mock_qdrant_hits, mock_pg_rows, mock_chunk_rows
):
    """Admin search should not impose a Qdrant filter (global view)."""
    with _patch_embedder() as mock_embedder_cls:
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768
        mock_embedder_cls.return_value = mock_embedder

        _setup_qdrant_mock(service, mock_qdrant_hits)
        _setup_db_mock_admin(service, mock_pg_rows, mock_chunk_rows)

        await service.search(query="Apple revenue Q3", owner_id=1, is_admin=True)
        _, kwargs = service.qdrant.query_points.call_args
        assert kwargs.get("query_filter") is None
