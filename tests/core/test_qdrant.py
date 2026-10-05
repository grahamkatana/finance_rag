from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qdrant_client.models import ScalarType

from app.core import qdrant as qdrant_module


@pytest.mark.asyncio
async def test_new_collection_is_created_with_int8_quantization_in_ram():
    """A new collection must be quantized: unquantized vectors get paged out of the memory-capped Qdrant pod."""
    fake = AsyncMock()
    fake.get_collections.return_value = MagicMock(collections=[])
    with patch.object(qdrant_module, "client", fake):
        await qdrant_module.init_qdrant()
    scalar = fake.create_collection.await_args.kwargs["quantization_config"].scalar
    assert scalar.type == ScalarType.INT8
    assert scalar.always_ram is True


@pytest.mark.asyncio
async def test_existing_collection_is_left_alone():
    fake = AsyncMock()
    existing = MagicMock()
    existing.name = qdrant_module.settings.qdrant_collection
    fake.get_collections.return_value = MagicMock(collections=[existing])
    with patch.object(qdrant_module, "client", fake):
        await qdrant_module.init_qdrant()
    fake.create_collection.assert_not_awaited()
