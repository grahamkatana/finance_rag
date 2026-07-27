import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def llm():
    with patch("openai.AsyncOpenAI"):
        from app.core.llm.providers.openai import OpenAICompatibleLLM
        return OpenAICompatibleLLM(
            api_key="test-key",
            model="gpt-4o",
            provider="openai",
        )


@pytest.fixture
def groq_llm():
    with patch("openai.AsyncOpenAI"):
        from app.core.llm.providers.openai import OpenAICompatibleLLM
        return OpenAICompatibleLLM(
            api_key="test-key",
            model="llama-3.3-70b-versatile",
            provider="groq",
        )


@pytest.fixture
def embedder():
    with patch("openai.AsyncOpenAI"):
        from app.core.llm.providers.openai import OpenAIEmbedder
        return OpenAIEmbedder(
            api_key="test-key",
            model="text-embedding-3-small",
            provider="openai",
        )


@pytest.mark.asyncio
async def test_stream_yields_tokens(llm):
    """stream() must yield tokens from OpenAI delta"""
    async def fake_stream(*args, **kwargs):
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Apple "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="revenue "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="grew."))]),
        ]
        for chunk in chunks:
            yield chunk

    llm.client.chat.completions.create = MagicMock(return_value=fake_stream())

    tokens = []
    async for token in llm.stream("What was Apple revenue?"):
        tokens.append(token)

    assert tokens == ["Apple ", "revenue ", "grew."]


@pytest.mark.asyncio
async def test_stream_skips_none_tokens(llm):
    """stream() must skip None delta content"""
    async def fake_stream(*args, **kwargs):
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
        ]
        for chunk in chunks:
            yield chunk

    llm.client.chat.completions.create = MagicMock(return_value=fake_stream())

    tokens = []
    async for token in llm.stream("test"):
        tokens.append(token)

    assert None not in tokens
    assert len(tokens) == 2


@pytest.mark.asyncio
async def test_complete_returns_string(llm):
    """complete() must return full string response"""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Apple net sales were $391B."
    llm.client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await llm.complete("What was Apple net sales?")
    assert isinstance(result, str)
    assert result == "Apple net sales were $391B."


@pytest.mark.asyncio
async def test_complete_handles_none_content(llm):
    """complete() must return empty string if content is None"""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = None
    llm.client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await llm.complete("test")
    assert result == ""


@pytest.mark.asyncio
async def test_embed_text_returns_vector(embedder):
    """embed_text() must return list of floats"""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3], index=0)]
    embedder.client.embeddings.create = AsyncMock(return_value=mock_response)

    result = await embedder.embed_text("Apple revenue Q3")
    assert isinstance(result, list)
    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_batch_returns_multiple_vectors(embedder):
    """embed_batch() must return one vector per text in order"""
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=[0.1, 0.2], index=0),
        MagicMock(embedding=[0.3, 0.4], index=1),
        MagicMock(embedding=[0.5, 0.6], index=2),
    ]
    embedder.client.embeddings.create = AsyncMock(return_value=mock_response)

    result = await embedder.embed_batch(["text1", "text2", "text3"])
    assert len(result) == 3
    assert result[0] == [0.1, 0.2]
    assert result[2] == [0.5, 0.6]


@pytest.mark.asyncio
async def test_embed_batch_single_api_call(embedder):
    """embed_batch() must use ONE API call"""
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=[0.1], index=0),
        MagicMock(embedding=[0.2], index=1),
    ]
    embedder.client.embeddings.create = AsyncMock(return_value=mock_response)

    await embedder.embed_batch(["text1", "text2"])
    assert embedder.client.embeddings.create.call_count == 1


def test_groq_uses_correct_base_url(groq_llm):
    """Groq provider must use Groq base URL"""
    from app.core.llm.providers.openai import OPENAI_COMPATIBLE_PROVIDERS
    assert OPENAI_COMPATIBLE_PROVIDERS["groq"]["base_url"] == "https://api.groq.com/openai/v1"


def test_openai_llm_implements_base_interface(llm):
    """OpenAICompatibleLLM must satisfy BaseLLM"""
    from app.core.llm.base import BaseLLM
    assert isinstance(llm, BaseLLM)


def test_openai_embedder_implements_base_interface(embedder):
    """OpenAIEmbedder must satisfy BaseEmbedder"""
    from app.core.llm.base import BaseEmbedder
    assert isinstance(embedder, BaseEmbedder)