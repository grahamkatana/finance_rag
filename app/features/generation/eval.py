import re

from app.core.config import settings
from app.core.llm.connector import get_llm
from app.core.prompts.helpers import build_faithfulness_prompt, build_relevance_prompt


class EvalService:
    def __init__(self):
        self.judge = get_llm(
            provider=settings.judge_provider,
            model=settings.judge_model,
            api_key=settings.judge_api_key,
            base_url=settings.judge_base_url,
        )

    def parse_score(self, response: str) -> float:
        if not response:
            return 0.0
        matches = re.findall(r"\d+\.?\d*", response)
        if not matches:
            return 0.0
        try:
            score = float(matches[0])
            return max(0.0, min(1.0, score))
        except ValueError:
            return 0.0

    async def evaluate(
        self,
        query: str,
        chunks: list[dict],
        answer: str,
    ) -> dict:
        if not answer.strip():
            return {
                "query": query,
                "faithfulness": 0.0,
                "relevance": 0.0,
                "chunks_evaluated": len(chunks),
            }

        if not chunks:
            return {
                "query": query,
                "faithfulness": 0.0,
                "relevance": 0.0,
                "chunks_evaluated": 0,
            }

        faithfulness_response = await self.judge.complete(
            build_faithfulness_prompt(answer=answer, chunks=chunks)
        )
        faithfulness = self.parse_score(faithfulness_response)

        relevance_response = await self.judge.complete(
            build_relevance_prompt(query=query, chunks=chunks)
        )
        relevance = self.parse_score(relevance_response)

        return {
            "query": query,
            "faithfulness": faithfulness,
            "relevance": relevance,
            "chunks_evaluated": len(chunks),
        }