import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.features.generation.eval import EvalService


@pytest.fixture
def eval_service():
    return EvalService()


@pytest.fixture
def mock_chunks():
    return [
        {
            "chunk_text": "Apple total net sales were 391 billion dollars in fiscal year 2024.",
            "file_name": "apple_10k.pdf",
            "chunk_index": 0,
            "source": "sec.gov",
            "score": 0.032,
        }
    ]


def test_eval_service_instantiates(eval_service):
    """EvalService should instantiate without errors"""
    assert eval_service is not None


def test_build_faithfulness_prompt(eval_service, mock_chunks):
    """Faithfulness prompt must contain answer and context"""
    prompt = eval_service.build_faithfulness_prompt(
        answer="Apple net sales were 391 billion dollars.",
        chunks=mock_chunks,
    )
    assert "391 billion" in prompt
    assert "apple_10k.pdf" in prompt
    assert isinstance(prompt, str)


def test_build_relevance_prompt(eval_service, mock_chunks):
    """Relevance prompt must contain query and chunk text"""
    prompt = eval_service.build_relevance_prompt(
        query="What was Apple total net sales in 2024?",
        chunks=mock_chunks,
    )
    assert "Apple" in prompt
    assert "net sales" in prompt
    assert isinstance(prompt, str)


def test_parse_score_valid(eval_service):
    """Score parser must extract float from LLM response"""
    assert eval_service.parse_score("Score: 0.85") == 0.85
    assert eval_service.parse_score("0.9") == 0.9
    assert eval_service.parse_score("The score is 0.75 out of 1.0") == 0.75


def test_parse_score_invalid_returns_zero(eval_service):
    """Invalid score response should return 0.0 not crash"""
    assert eval_service.parse_score("I cannot score this") == 0.0
    assert eval_service.parse_score("") == 0.0
    assert eval_service.parse_score("N/A") == 0.0


def test_parse_score_clamps_to_range(eval_service):
    """Score must always be between 0.0 and 1.0"""
    assert eval_service.parse_score("1.5") <= 1.0
    assert eval_service.parse_score("-0.5") >= 0.0


@pytest.mark.asyncio
async def test_evaluate_returns_scores(eval_service, mock_chunks):
    """Evaluate must return faithfulness and relevance scores"""
    with patch("app.features.generation.eval.ollama.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.message.content = "Score: 0.85"
        mock_client.chat = AsyncMock(return_value=mock_response)

        result = await eval_service.evaluate(
            query="What was Apple net sales in 2024?",
            chunks=mock_chunks,
            answer="Apple net sales were 391 billion dollars.",
        )

    assert "faithfulness" in result
    assert "relevance" in result
    assert "query" in result
    assert isinstance(result["faithfulness"], float)
    assert isinstance(result["relevance"], float)


@pytest.mark.asyncio
async def test_evaluate_scores_in_range(eval_service, mock_chunks):
    """All scores must be between 0.0 and 1.0"""
    with patch("app.features.generation.eval.ollama.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.message.content = "Score: 0.9"
        mock_client.chat = AsyncMock(return_value=mock_response)

        result = await eval_service.evaluate(
            query="What was Apple net sales in 2024?",
            chunks=mock_chunks,
            answer="Apple net sales were 391 billion dollars.",
        )

    assert 0.0 <= result["faithfulness"] <= 1.0
    assert 0.0 <= result["relevance"] <= 1.0


@pytest.mark.asyncio
async def test_evaluate_empty_answer(eval_service, mock_chunks):
    """Empty answer should return low faithfulness score"""
    with patch("app.features.generation.eval.ollama.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.message.content = "Score: 0.0"
        mock_client.chat = AsyncMock(return_value=mock_response)

        result = await eval_service.evaluate(
            query="What was Apple net sales in 2024?",
            chunks=mock_chunks,
            answer="",
        )

    assert result["faithfulness"] == 0.0


@pytest.mark.asyncio
async def test_evaluate_empty_chunks(eval_service):
    """Empty chunks should return zero relevance"""
    with patch("app.features.generation.eval.ollama.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.message.content = "Score: 0.0"
        mock_client.chat = AsyncMock(return_value=mock_response)

        result = await eval_service.evaluate(
            query="What was Apple net sales in 2024?",
            chunks=[],
            answer="I don't know.",
        )

    assert result["relevance"] == 0.0