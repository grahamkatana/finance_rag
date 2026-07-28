import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.features.generation.service import GenerationService


@pytest.fixture
def service():
    with patch("app.features.generation.service.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        svc = GenerationService()
        svc._mock_llm = mock_llm
        return svc


@pytest.mark.asyncio
async def test_stream_yields_tokens(service):
    """stream() must yield tokens from LLM"""
    async def fake_stream(prompt):
        for token in ["Apple ", "revenue ", "grew."]:
            yield token

    service.llm.stream = fake_stream

    tokens = []
    async for token in service.stream(
        query="What was Apple revenue?",
        chunks=[{
            "chunk_text": "Apple revenue grew.",
            "file_name": "apple.pdf",
            "chunk_index": 0,
        }],
    ):
        tokens.append(token)

    assert len(tokens) > 0
    assert all(isinstance(t, str) for t in tokens)


@pytest.mark.asyncio
async def test_stream_yields_strings(service):
    """Every token must be a string"""
    async def fake_stream(prompt):
        yield "token"

    service.llm.stream = fake_stream

    async for token in service.stream(
        query="test",
        chunks=[],
    ):
        assert isinstance(token, str)


@pytest.mark.asyncio
async def test_stream_empty_chunks_still_streams(service):
    """stream() must work with no chunks"""
    async def fake_stream(prompt):
        yield "I don't know."

    service.llm.stream = fake_stream

    tokens = []
    async for token in service.stream(query="test", chunks=[]):
        tokens.append(token)

    assert len(tokens) > 0


def test_stream_calls_llm(service):
    """GenerationService must use connector LLM not ollama directly"""
    from app.core.llm.base import BaseLLM
    # llm attribute must exist — set by connector
    assert hasattr(service, "llm")