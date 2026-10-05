import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.prompts.helpers import build_generation_prompt
from app.features.generation import history as history_module
from app.features.generation.history import format_history, standalone_query

HISTORY = [
    {"role": "user", "content": "What was Apple's total net sales in fiscal 2024?"},
    {"role": "assistant", "content": "Total net sales were $391.0 billion [Source 1], up 2% (Source 2)."},
]
CHUNK = {"chunk_text": "Services net sales were $96,169 million.", "file_name": "10k.pdf", "chunk_index": 7}


def _llm(reply=None, error=None):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=reply, side_effect=error)
    return patch("app.features.generation.history.get_llm", return_value=llm), llm


# ---- format_history ----

def test_format_history_labels_roles_and_drops_source_numbers():
    text = format_history(HISTORY)
    assert text.splitlines()[0] == "User: What was Apple's total net sales in fiscal 2024?"
    assert text.splitlines()[1] == "Assistant: Total net sales were $391.0 billion, up 2%."  # [Source 1] / (Source 2) gone
    assert "Source" not in text


def test_format_history_cuts_a_very_long_earlier_answer():
    long_answer = "word " * 1000
    text = format_history([{"role": "assistant", "content": long_answer}])
    assert len(text) < history_module.MAX_TURN_CHARS + 30 and text.endswith("…")


# ---- standalone_query ----

@pytest.mark.asyncio
async def test_a_first_question_is_returned_untouched_without_calling_the_model():
    patcher, llm = _llm("should not be used")
    with patcher as get_llm:
        assert await standalone_query([], "What was net sales?") == "What was net sales?"
    get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_a_follow_up_is_rewritten_and_the_prompt_carries_the_conversation():
    patcher, llm = _llm("What were Apple's services net sales in fiscal 2024?")
    with patcher:
        result = await standalone_query(HISTORY, "And services?")
    assert result == "What were Apple's services net sales in fiscal 2024?"
    prompt = llm.complete.await_args.args[0]
    assert "And services?" in prompt and "total net sales in fiscal 2024" in prompt and "$391.0 billion" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("reply,expected", [
    ('"What were services net sales?"', "What were services net sales?"),
    ("STANDALONE QUESTION: What were services net sales?", "What were services net sales?"),
    ("\n\n  What were services net sales?\nExtra commentary the model added.", "What were services net sales?"),
    ("```What were services net sales?```", "What were services net sales?"),
])
async def test_the_models_reply_is_cleaned_to_one_plain_question(reply, expected):
    patcher, _ = _llm(reply)
    with patcher:
        assert await standalone_query(HISTORY, "And services?") == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", ["", "   \n ", None, "x " * 400])
async def test_an_empty_or_rambling_rewrite_falls_back_to_what_the_user_typed(reply):
    patcher, _ = _llm(reply)
    with patcher:
        assert await standalone_query(HISTORY, "And services?") == "And services?"


@pytest.mark.asyncio
async def test_a_failing_model_never_fails_the_question():
    patcher, _ = _llm(error=RuntimeError("model unavailable"))
    with patcher:
        assert await standalone_query(HISTORY, "And services?") == "And services?"


@pytest.mark.asyncio
async def test_a_slow_model_is_given_up_on():
    async def slow(prompt):
        await asyncio.sleep(5)
        return "too late"

    llm = MagicMock()
    llm.complete = slow
    with patch("app.features.generation.history.get_llm", return_value=llm), \
         patch.object(history_module, "CONDENSE_TIMEOUT_SECONDS", 0.05):
        assert await standalone_query(HISTORY, "And services?") == "And services?"


# ---- the answer prompt ----

def test_prompt_without_history_is_the_original_prompt():
    prompt = build_generation_prompt(query="What was net sales?", chunks=[CHUNK])
    assert "Earlier conversation" not in prompt and "Question: What was net sales?" in prompt


def test_prompt_with_history_includes_the_conversation_and_both_phrasings():
    prompt = build_generation_prompt(
        query="What were Apple's services net sales in fiscal 2024?", chunks=[CHUNK], history=HISTORY, asked="And services?",
    )
    assert "Earlier conversation:" in prompt and "User: What was Apple's total net sales in fiscal 2024?" in prompt
    assert "The user's latest message: And services?" in prompt
    assert "it is asking: What were Apple's services net sales in fiscal 2024?" in prompt
    assert "[Source 1]" not in prompt  # old source numbers must not leak into a new search's numbering
    assert "[Source 1: 10k.pdf chunk 7]" in prompt  # the new search's own numbering
    assert "Never take facts" in prompt


def test_prompt_with_history_but_no_passages_still_says_nothing_was_found():
    prompt = build_generation_prompt(query="q", chunks=[], history=HISTORY, asked="q")
    assert "could not find relevant information" in prompt.lower() or "no context available" in prompt.lower()
