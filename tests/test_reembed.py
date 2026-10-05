from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.reembed import reembed_all


def _row(i, owner_id=1):
    return MagicMock(qdrant_id=f"id-{i}", file_name="10k.pdf", chunk_index=i, source="sec.gov", owner_id=owner_id, chunk_text=f"text {i}")


@pytest.mark.asyncio
async def test_reembed_keeps_point_ids_and_payload_and_batches():
    """Every chunk is re-embedded under its EXISTING point id with the same payload, in batches."""
    rows = [_row(i, owner_id=7) for i in range(5)]
    result = MagicMock()
    result.fetchall.return_value = rows
    db = AsyncMock()
    db.execute.return_value = result
    qdrant = AsyncMock()
    embedder = AsyncMock()
    embedder.embed_batch.side_effect = lambda texts: [[float(len(t))] for t in texts]

    count = await reembed_all(db, qdrant, embedder, batch_size=2)

    assert count == 5
    assert [len(c.args[0]) for c in embedder.embed_batch.await_args_list] == [2, 2, 1]
    points = [p for c in qdrant.upsert.await_args_list for p in c.kwargs["points"]]
    assert [p.id for p in points] == [f"id-{i}" for i in range(5)]
    assert points[3].payload == {"file_name": "10k.pdf", "chunk_index": 3, "source": "sec.gov", "owner_id": 7}
    assert all(c.kwargs["collection_name"] == settings.qdrant_collection for c in qdrant.upsert.await_args_list)


@pytest.mark.asyncio
async def test_reembed_with_no_documents_does_nothing():
    result = MagicMock()
    result.fetchall.return_value = []
    db = AsyncMock()
    db.execute.return_value = result
    qdrant, embedder = AsyncMock(), AsyncMock()

    assert await reembed_all(db, qdrant, embedder) == 0
    qdrant.upsert.assert_not_awaited()
    embedder.embed_batch.assert_not_awaited()
