import pytest
from unittest.mock import AsyncMock, MagicMock, patch, MagicMock
import sys


def make_mock_genai():
    """Create a mock google.generativeai module"""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_genai():
    mock = make_mock_genai()
    # Inject into sys.modules so import works
    sys.modules["google.generativeai"] = mock
    yield mock
    # Clean up
    sys.modules.pop("google.generativeai", None)


@pytest.fixture
def llm(mock_genai):
    from app.core.llm.providers.gemini import GeminiLLM
    instance = GeminiLLM.__new__(GeminiLLM)
    instance._genai = mock_genai
    instance.model = "gemini-2.0-flash"
    return instance


@pytest.fixture
def embedder(mock_genai):
    from app.core.llm.providers.gemini import GeminiEmbedder
    instance = GeminiEmbedder.__new__(GeminiEmbedder)
    instance._genai = mock_genai
    instance.model = "models/text-embedding-005"
    return instance


@pytest.mark.asyncio
async def test_gemini_stream_yields_tokens(llm):
    """stream() must yield text chunks from Gemini"""
    async def fake_stream():
        for text in ["Apple ", "revenue ", "grew."]:
            yield MagicMock(text=text)

    mock_model = MagicMock()
    mock_model.generate_content_async.return_value = fake_stream()
    llm._genai.GenerativeModel.return_value = mock_model
    llm._genai.GenerationConfig.return_value = {}

    tokens = []
    async for token in llm.stream("What was Apple revenue?"):
        tokens.append(token)

    assert tokens == ["Apple ", "revenue ", "grew."]


@pytest.mark.asyncio
async def test_gemini_stream_skips_empty_text(llm):
    """stream() must skip chunks with empty text"""
    async def fake_stream():
        for text in ["Hello", "", " world"]:
            yield MagicMock(text=text)

    mock_model = MagicMock()
    mock_model.generate_content_async.return_value = fake_stream()
    llm._genai.GenerativeModel.return_value = mock_model
    llm._genai.GenerationConfig.return_value = {}

    tokens = []
    async for token in llm.stream("test"):
        tokens.append(token)

    assert "" not in tokens
    assert len(tokens) == 2


@pytest.mark.asyncio
async def test_gemini_complete_returns_string(llm):
    """complete() must return full response text"""
    mock_response = MagicMock()
    mock_response.text = "Apple net sales were $391B."

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    llm._genai.GenerativeModel.return_value = mock_model
    llm._genai.GenerationConfig.return_value = {}

    result = await llm.complete("What was Apple net sales?")
    assert isinstance(result, str)
    assert result == "Apple net sales were $391B."


@pytest.mark.asyncio
async def test_gemini_complete_handles_none_text(llm):
    """complete() must return empty string if text is None"""
    mock_response = MagicMock()
    mock_response.text = None

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    llm._genai.GenerativeModel.return_value = mock_model
    llm._genai.GenerationConfig.return_value = {}

    result = await llm.complete("test")
    assert result == ""


@pytest.mark.asyncio
async def test_gemini_embed_text_returns_vector(embedder):
    """embed_text() must return list of floats"""
    embedder._genai.embed_content.return_value = {"embedding": [0.1, 0.2, 0.3]}

    result = await embedder.embed_text("Apple revenue Q3")
    assert isinstance(result, list)
    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_gemini_embed_batch_returns_multiple_vectors(embedder):
    """embed_batch() must return one vector per text"""
    embedder._genai.embed_content.side_effect = [
        {"embedding": [0.1, 0.2]},
        {"embedding": [0.3, 0.4]},
        {"embedding": [0.5, 0.6]},
    ]

    result = await embedder.embed_batch(["text1", "text2", "text3"])
    assert len(result) == 3
    assert result[0] == [0.1, 0.2]
    assert result[2] == [0.5, 0.6]


@pytest.mark.asyncio
async def test_gemini_embed_batch_runs_concurrently(embedder):
    """embed_batch() must call embed_content for each text"""
    embedder._genai.embed_content.side_effect = [
        {"embedding": [0.1]},
        {"embedding": [0.2]},
    ]

    result = await embedder.embed_batch(["text1", "text2"])
    assert embedder._genai.embed_content.call_count == 2


def test_gemini_llm_implements_base_interface(llm):
    """GeminiLLM must satisfy BaseLLM"""
    from app.core.llm.base import BaseLLM
    assert isinstance(llm, BaseLLM)


def test_gemini_embedder_implements_base_interface(embedder):
    """GeminiEmbedder must satisfy BaseEmbedder"""
    from app.core.llm.base import BaseEmbedder
    assert isinstance(embedder, BaseEmbedder)