import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.llm.providers.ollama import OllamaLLM, OllamaEmbedder


@pytest.fixture
def llm():
    return OllamaLLM(base_url="http://localhost:11434", model="phi4-mini")


@pytest.fixture
def embedder():
    return OllamaEmbedder(base_url="http://localhost:11434", model="nomic-embed-text")


@pytest.mark.asyncio
async def test_ollama_llm_stream_yields_tokens(llm):
    """stream() must yield string tokens"""
    with patch.object(llm, "client") as mock_client:
        async def fake_chat(*args, **kwargs):
            chunks = [
                MagicMock(message=MagicMock(content="Apple ")),
                MagicMock(message=MagicMock(content="revenue ")),
                MagicMock(message=MagicMock(content="grew.")),
            ]
            for chunk in chunks:
                yield chunk

        mock_client.chat.return_value = fake_chat()

        tokens = []
        async for token in llm.stream("What was Apple revenue?"):
            tokens.append(token)

        assert tokens == ["Apple ", "revenue ", "grew."]


@pytest.mark.asyncio
async def test_ollama_llm_stream_skips_empty_tokens(llm):
    """stream() must skip empty string tokens"""
    with patch.object(llm, "client") as mock_client:
        async def fake_chat(*args, **kwargs):
            chunks = [
                MagicMock(message=MagicMock(content="Hello")),
                MagicMock(message=MagicMock(content="")),
                MagicMock(message=MagicMock(content=" world")),
            ]
            for chunk in chunks:
                yield chunk

        mock_client.chat.return_value = fake_chat()

        tokens = []
        async for token in llm.stream("test"):
            tokens.append(token)

        assert "" not in tokens
        assert len(tokens) == 2


@pytest.mark.asyncio
async def test_ollama_llm_complete_returns_string(llm):
    """complete() must return a string"""
    with patch.object(llm, "client") as mock_client:
        mock_response = MagicMock()
        mock_response.message.content = "Apple net sales were $391B."
        mock_client.chat = AsyncMock(return_value=mock_response)

        result = await llm.complete("What was Apple net sales?")
        assert isinstance(result, str)
        assert result == "Apple net sales were $391B."


@pytest.mark.asyncio
async def test_ollama_llm_complete_handles_none_content(llm):
    """complete() must return empty string if content is None"""
    with patch.object(llm, "client") as mock_client:
        mock_response = MagicMock()
        mock_response.message.content = None
        mock_client.chat = AsyncMock(return_value=mock_response)

        result = await llm.complete("test")
        assert result == ""


@pytest.mark.asyncio
async def test_ollama_embedder_embed_text_returns_vector(embedder):
    """embed_text() must return a list of floats"""
    with patch.object(embedder, "client") as mock_client:
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3]]
        mock_client.embed = AsyncMock(return_value=mock_response)

        result = await embedder.embed_text("Apple revenue Q3")
        assert isinstance(result, list)
        assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_ollama_embedder_embed_batch_returns_multiple_vectors(embedder):
    """embed_batch() must return one vector per text"""
    with patch.object(embedder, "client") as mock_client:
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        mock_client.embed = AsyncMock(return_value=mock_response)

        texts = ["text1", "text2", "text3"]
        result = await embedder.embed_batch(texts)

        assert len(result) == 3
        assert result[0] == [0.1, 0.2]
        assert result[2] == [0.5, 0.6]


@pytest.mark.asyncio
async def test_ollama_embedder_single_call_for_batch(embedder):
    """embed_batch() must use ONE API call not N calls"""
    with patch.object(embedder, "client") as mock_client:
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1], [0.2]]
        mock_client.embed = AsyncMock(return_value=mock_response)

        await embedder.embed_batch(["text1", "text2"])

        # Must only call embed once
        assert mock_client.embed.call_count == 1


def test_ollama_llm_implements_base_interface(llm):
    """OllamaLLM must satisfy BaseLLM interface"""
    from app.core.llm.base import BaseLLM
    assert isinstance(llm, BaseLLM)


def test_ollama_embedder_implements_base_interface(embedder):
    """OllamaEmbedder must satisfy BaseEmbedder interface"""
    from app.core.llm.base import BaseEmbedder
    assert isinstance(embedder, BaseEmbedder)