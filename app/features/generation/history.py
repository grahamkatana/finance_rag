"""
Follow-up questions.

A chat is a list of messages, but retrieval and answering both work from
one question at a time, so a follow-up like "and services?" or "why?" has to
be turned into something that can be searched for. Two pieces:

  * standalone_query() asks the answer model to rewrite the latest question
    using the last few messages, and that rewrite is what gets embedded and
    searched. It is skipped for the first question of a chat (nothing to
    resolve) and falls back to the user's own words if the model fails.
  * format_history() renders those messages for the answer prompt, so the
    model can also honour requests that are about the answer itself
    ("shorter", "as a table").
"""

import asyncio
import re

from app.core.config import settings
from app.core.llm.connector import get_llm
from app.core.logging import logger
from app.core.prompts.loader import load_prompt

log = logger.getChild("generation.history")

HISTORY_MESSAGES = 6          # last three exchanges
MAX_TURN_CHARS = 1200         # a long earlier answer is cut, not sent whole
MAX_QUERY_CHARS = 500         # a "rewrite" longer than this is the model rambling
CONDENSE_TIMEOUT_SECONDS = 20

# "[Source 1]", "(Source 2)", "[Sources 1, 3]": numbers that only mean something
# for the search that produced that answer, and would mislead in a new one.
_CITATION = re.compile(r"\s*[\[(]\s*Sources?\s*\d+(?:\s*(?:,|&|and)\s*(?:Sources?\s*)?\d+)*\s*[\])]", re.IGNORECASE)


def format_history(history: list[dict]) -> str:
    lines = []
    for message in history:
        text = _CITATION.sub("", message["content"]).strip()
        if len(text) > MAX_TURN_CHARS:
            text = text[:MAX_TURN_CHARS].rsplit(" ", 1)[0] + "…"
        lines.append(f"{'User' if message['role'] == 'user' else 'Assistant'}: {text}")
    return "\n".join(lines)


def _one_line(raw: str) -> str:
    for line in (raw or "").splitlines():
        line = line.strip().strip("`\"'“”").strip()
        line = re.sub(r"^(standalone question|rewritten question)\s*:\s*", "", line, flags=re.IGNORECASE)
        if line:
            return line
    return ""


async def standalone_query(history: list[dict], query: str) -> str:
    """The latest question rewritten so it can be searched without the conversation."""
    if not history:
        return query
    try:
        llm = get_llm(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            kind="rewrite",
        )
        raw = await asyncio.wait_for(
            llm.complete(load_prompt("condense").format(history=format_history(history), query=query)),
            timeout=CONDENSE_TIMEOUT_SECONDS,
        )
    except Exception as e:
        # A failed rewrite must not fail the question: search with the user's own words.
        log.warning(f"Could not rewrite the follow-up question, using it as typed: {e}")
        return query
    rewritten = _one_line(raw)
    if not rewritten or len(rewritten) > MAX_QUERY_CHARS:
        return query
    return rewritten
