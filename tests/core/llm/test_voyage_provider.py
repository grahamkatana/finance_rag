import pytest
import sys
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_voyageai():
    mock = MagicMock()
    sys.modules["voyageai"] = mock
    yield mock
    sys.modules.pop("voyageai", None)


@pytest.fixture
def embedder(mock_voyageai):
    from app.core.llm.providers.voyage import VoyageEmbedder
    instance = VoyageEmbedder.__new__(VoyageEmbedder)
    instance._client = MagicMock()
    instance.model = "voyage-4"
    return instance


@pytest.mark.asyncio
async def test_voyage_embed_text_returns_vector(embedder):
    """embed_text() must return list of floats"""
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1, 0.2, 0.3]]
    embedder._client.embed = AsyncMock(return_value=mock_result)

    result = await embedder.embed_text("Apple revenue Q3")
    assert isinstance(result, list)
    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_voyage_embed_text_uses_query_input_type(embedder):
    """embed_text() must use input_type=query for search optimization"""
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1]]
    embedder._client.embed = AsyncMock(return_value=mock_result)

    await embedder.embed_text("What was Apple revenue?")

    call_kwargs = embedder._client.embed.call_args.kwargs
    assert call_kwargs["input_type"] == "query"


@pytest.mark.asyncio
async def test_voyage_embed_batch_returns_multiple_vectors(embedder):
    """embed_batch() must return one vector per text"""
    mock_result = MagicMock()
    mock_result.embeddings = [
        [0.1, 0.2],
        [0.3, 0.4],
        [0.5, 0.6],
    ]
    embedder._client.embed = AsyncMock(return_value=mock_result)

    result = await embedder.embed_batch(["text1", "text2", "text3"])
    assert len(result) == 3
    assert result[0] == [0.1, 0.2]
    assert result[2] == [0.5, 0.6]


@pytest.mark.asyncio
async def test_voyage_embed_batch_uses_document_input_type(embedder):
    """embed_batch() must use input_type=document for ingestion optimization"""
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1], [0.2]]
    embedder._client.embed = AsyncMock(return_value=mock_result)

    await embedder.embed_batch(["chunk1", "chunk2"])

    call_kwargs = embedder._client.embed.call_args.kwargs
    assert call_kwargs["input_type"] == "document"


@pytest.mark.asyncio
async def test_voyage_embed_batch_single_api_call(embedder):
    """embed_batch() must use ONE API call — native batch"""
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1], [0.2]]
    embedder._client.embed = AsyncMock(return_value=mock_result)

    await embedder.embed_batch(["text1", "text2"])
    assert embedder._client.embed.call_count == 1


@pytest.mark.asyncio
async def test_voyage_embed_text_wraps_in_list(embedder):
    """embed_text() must send text as list to Voyage API"""
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1]]
    embedder._client.embed = AsyncMock(return_value=mock_result)

    await embedder.embed_text("single text")

    call_kwargs = embedder._client.embed.call_args.kwargs
    assert isinstance(call_kwargs["texts"], list)
    assert len(call_kwargs["texts"]) == 1


def test_voyage_embedder_implements_base_interface(embedder):
    """VoyageEmbedder must satisfy BaseEmbedder"""
    from app.core.llm.base import BaseEmbedder
    assert isinstance(embedder, BaseEmbedder)


def test_voyage_has_no_llm_class():
    """Voyage AI is embeddings only — no LLM class"""
    import app.core.llm.providers.voyage as voyage_module
    assert not hasattr(voyage_module, "VoyageLLM")