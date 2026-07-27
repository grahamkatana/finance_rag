import pytest
import sys
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_mistralai():
    mock = MagicMock()
    sys.modules["mistralai"] = mock
    yield mock
    sys.modules.pop("mistralai", None)


@pytest.fixture
def llm(mock_mistralai):
    from app.core.llm.providers.mistral import MistralLLM
    instance = MistralLLM.__new__(MistralLLM)
    instance._client = MagicMock()
    instance.model = "mistral-large-latest"
    return instance


@pytest.fixture
def embedder(mock_mistralai):
    from app.core.llm.providers.mistral import MistralEmbedder
    instance = MistralEmbedder.__new__(MistralEmbedder)
    instance._client = MagicMock()
    instance.model = "mistral-embed"
    return instance


@pytest.mark.asyncio
async def test_mistral_stream_yields_tokens(llm):
    """stream() must yield tokens from Mistral events"""
    async def fake_stream(*args, **kwargs):
        events = [
            MagicMock(data=MagicMock(choices=[MagicMock(delta=MagicMock(content="Apple "))])),
            MagicMock(data=MagicMock(choices=[MagicMock(delta=MagicMock(content="revenue "))])),
            MagicMock(data=MagicMock(choices=[MagicMock(delta=MagicMock(content="grew."))])),
        ]
        for event in events:
            yield event

    llm._client.chat.stream_async = MagicMock(return_value=fake_stream())

    tokens = []
    async for token in llm.stream("What was Apple revenue?"):
        tokens.append(token)

    assert tokens == ["Apple ", "revenue ", "grew."]


@pytest.mark.asyncio
async def test_mistral_stream_skips_none_tokens(llm):
    """stream() must skip None content"""
    async def fake_stream(*args, **kwargs):
        events = [
            MagicMock(data=MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))])),
            MagicMock(data=MagicMock(choices=[MagicMock(delta=MagicMock(content=None))])),
            MagicMock(data=MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))])),
        ]
        for event in events:
            yield event

    llm._client.chat.stream_async = MagicMock(return_value=fake_stream())

    tokens = []
    async for token in llm.stream("test"):
        tokens.append(token)

    assert None not in tokens
    assert len(tokens) == 2


@pytest.mark.asyncio
async def test_mistral_complete_returns_string(llm):
    """complete() must return full response"""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Apple net sales were $391B."
    llm._client.chat.complete_async = AsyncMock(return_value=mock_response)

    result = await llm.complete("What was Apple net sales?")
    assert isinstance(result, str)
    assert result == "Apple net sales were $391B."


@pytest.mark.asyncio
async def test_mistral_complete_handles_none_content(llm):
    """complete() must return empty string if content is None"""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = None
    llm._client.chat.complete_async = AsyncMock(return_value=mock_response)

    result = await llm.complete("test")
    assert result == ""


@pytest.mark.asyncio
async def test_mistral_embed_text_returns_vector(embedder):
    """embed_text() must return list of floats"""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
    embedder._client.embeddings.create_async = AsyncMock(return_value=mock_response)

    result = await embedder.embed_text("Apple revenue Q3")
    assert isinstance(result, list)
    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_mistral_embed_text_uses_list_input(embedder):
    """embed_text() must wrap text in list — Mistral uses 'inputs' plural"""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1])]
    embedder._client.embeddings.create_async = AsyncMock(return_value=mock_response)

    await embedder.embed_text("test")

    call_kwargs = embedder._client.embeddings.create_async.call_args.kwargs
    assert "inputs" in call_kwargs
    assert isinstance(call_kwargs["inputs"], list)


@pytest.mark.asyncio
async def test_mistral_embed_batch_returns_multiple_vectors(embedder):
    """embed_batch() must return one vector per text"""
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=[0.1, 0.2]),
        MagicMock(embedding=[0.3, 0.4]),
        MagicMock(embedding=[0.5, 0.6]),
    ]
    embedder._client.embeddings.create_async = AsyncMock(return_value=mock_response)

    result = await embedder.embed_batch(["text1", "text2", "text3"])
    assert len(result) == 3
    assert result[0] == [0.1, 0.2]
    assert result[2] == [0.5, 0.6]


@pytest.mark.asyncio
async def test_mistral_embed_batch_single_api_call(embedder):
    """embed_batch() must use ONE API call — native batch support"""
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=[0.1]),
        MagicMock(embedding=[0.2]),
    ]
    embedder._client.embeddings.create_async = AsyncMock(return_value=mock_response)

    await embedder.embed_batch(["text1", "text2"])
    assert embedder._client.embeddings.create_async.call_count == 1


def test_mistral_llm_implements_base_interface(llm):
    """MistralLLM must satisfy BaseLLM"""
    from app.core.llm.base import BaseLLM
    assert isinstance(llm, BaseLLM)


def test_mistral_embedder_implements_base_interface(embedder):
    """MistralEmbedder must satisfy BaseEmbedder"""
    from app.core.llm.base import BaseEmbedder
    assert isinstance(embedder, BaseEmbedder)