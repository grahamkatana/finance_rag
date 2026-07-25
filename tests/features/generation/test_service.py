import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.features.generation.service import GenerationService


@pytest.fixture
def mock_chunks():
    return [
        {
            "chunk_text": "Apple revenue grew 12% in Q3 2023.",
            "file_name": "apple_10k.pdf",
            "chunk_index": 1,
            "source": "sec.gov",
            "score": 0.032,
        },
        {
            "chunk_text": "Net income rose to $19.9 billion.",
            "file_name": "apple_10k.pdf",
            "chunk_index": 2,
            "source": "sec.gov",
            "score": 0.028,
        },
    ]


@pytest.fixture
def service():
    return GenerationService()


def test_build_prompt_contains_query(service, mock_chunks):
    """Prompt must contain the user query"""
    prompt = service.build_prompt(
        query="What was Apple revenue in Q3?",
        chunks=mock_chunks,
    )
    assert "What was Apple revenue in Q3?" in prompt


def test_build_prompt_contains_chunk_text(service, mock_chunks):
    """Prompt must contain retrieved chunk text"""
    prompt = service.build_prompt(
        query="What was Apple revenue in Q3?",
        chunks=mock_chunks,
    )
    assert "Apple revenue grew 12% in Q3 2023." in prompt
    assert "Net income rose to $19.9 billion." in prompt


def test_build_prompt_contains_all_sources(service, mock_chunks):
    """Prompt must reference source files for grounding"""
    prompt = service.build_prompt(
        query="What was Apple revenue in Q3?",
        chunks=mock_chunks,
    )
    assert "apple_10k.pdf" in prompt


def test_build_prompt_empty_chunks(service):
    """Empty chunks should still build a valid prompt"""
    prompt = service.build_prompt(
        query="What was Apple revenue in Q3?",
        chunks=[],
    )
    assert "What was Apple revenue in Q3?" in prompt
    assert isinstance(prompt, str)


def test_build_prompt_returns_string(service, mock_chunks):
    """build_prompt must always return a string"""
    result = service.build_prompt(
        query="What was Apple revenue?",
        chunks=mock_chunks,
    )
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_stream_calls_ollama(service, mock_chunks):
    """Stream must call Ollama chat with the built prompt"""
    with patch("app.features.generation.service.ollama.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        async def fake_stream(*args, **kwargs):
            chunks = [
                MagicMock(message=MagicMock(content="Apple ")),
                MagicMock(message=MagicMock(content="revenue ")),
                MagicMock(message=MagicMock(content="grew.")),
            ]
            for chunk in chunks:
                yield chunk

        mock_client.chat.return_value = fake_stream()

        tokens = []
        async for token in service.stream(
            query="What was Apple revenue?",
            chunks=mock_chunks,
        ):
            tokens.append(token)

        assert len(tokens) > 0


@pytest.mark.asyncio
async def test_stream_yields_strings(service, mock_chunks):
    """Every token yielded must be a string"""
    with patch("app.features.generation.service.ollama.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        async def fake_stream(*args, **kwargs):
            chunks = [
                MagicMock(message=MagicMock(content="Apple ")),
                MagicMock(message=MagicMock(content="revenue ")),
            ]
            for chunk in chunks:
                yield chunk

        mock_client.chat.return_value = fake_stream()

        async for token in service.stream(
            query="What was Apple revenue?",
            chunks=mock_chunks,
        ):
            assert isinstance(token, str)


@pytest.mark.asyncio
async def test_stream_empty_chunks_still_streams(service):
    """Generation should still work with no retrieved chunks"""
    with patch("app.features.generation.service.ollama.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        async def fake_stream(*args, **kwargs):
            yield MagicMock(message=MagicMock(content="I don't know."))

        mock_client.chat.return_value = fake_stream()

        tokens = []
        async for token in service.stream(
            query="What was Apple revenue?",
            chunks=[],
        ):
            tokens.append(token)

        assert len(tokens) > 0