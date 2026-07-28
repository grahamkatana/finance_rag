import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.features.generation.eval import EvalService
from app.core.prompts.helpers import (
    build_faithfulness_prompt,
    build_relevance_prompt,
)


@pytest.fixture
def eval_service():
    with patch("app.features.generation.eval.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        return EvalService()


@pytest.fixture
def mock_chunks():
    return [
        {
            "chunk_text": "Apple total net sales were $391,035 million.",
            "file_name": "apple_10k.pdf",
            "chunk_index": 0,
            "source": "sec.gov",
            "score": 0.032,
        }
    ]


def test_eval_service_instantiates(eval_service):
    """EvalService should instantiate without errors"""
    assert eval_service is not None


def test_build_faithfulness_prompt(mock_chunks):
    """Faithfulness prompt must contain answer and context"""
    prompt = build_faithfulness_prompt(
        answer="Apple net sales were $391,035 million.",
        chunks=mock_chunks,
    )
    assert "391,035" in prompt
    assert "apple_10k.pdf" in prompt
    assert isinstance(prompt, str)


def test_build_relevance_prompt(mock_chunks):
    """Relevance prompt must contain query and chunk text"""
    prompt = build_relevance_prompt(
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
    """Invalid score response should return 0.0"""
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
    eval_service.judge.complete = AsyncMock(return_value="Score: 0.85")

    result = await eval_service.evaluate(
        query="What was Apple net sales in 2024?",
        chunks=mock_chunks,
        answer="Apple net sales were $391,035 million.",
    )

    assert "faithfulness" in result
    assert "relevance" in result
    assert "query" in result
    assert isinstance(result["faithfulness"], float)
    assert isinstance(result["relevance"], float)


@pytest.mark.asyncio
async def test_evaluate_scores_in_range(eval_service, mock_chunks):
    """All scores must be between 0.0 and 1.0"""
    eval_service.judge.complete = AsyncMock(return_value="Score: 0.9")

    result = await eval_service.evaluate(
        query="What was Apple net sales in 2024?",
        chunks=mock_chunks,
        answer="Apple net sales were $391,035 million.",
    )

    assert 0.0 <= result["faithfulness"] <= 1.0
    assert 0.0 <= result["relevance"] <= 1.0


@pytest.mark.asyncio
async def test_evaluate_empty_answer(eval_service, mock_chunks):
    """Empty answer should return zero scores"""
    result = await eval_service.evaluate(
        query="What was Apple net sales in 2024?",
        chunks=mock_chunks,
        answer="",
    )
    assert result["faithfulness"] == 0.0


@pytest.mark.asyncio
async def test_evaluate_empty_chunks(eval_service):
    """Empty chunks should return zero scores"""
    result = await eval_service.evaluate(
        query="What was Apple net sales in 2024?",
        chunks=[],
        answer="I don't know.",
    )
    assert result["relevance"] == 0.0