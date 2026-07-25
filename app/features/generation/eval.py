import re

import ollama

from app.core.config import settings


class EvalService:
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.judge_model = settings.ollama_judge_model

    def build_faithfulness_prompt(
        self,
        answer: str,
        chunks: list[dict],
    ) -> str:
        """
        Asks the judge: is this answer grounded in the context?
        Score 1.0 = fully grounded, 0.0 = completely hallucinated.
        """
        context = "\n\n".join([
            f"[Source: {c['file_name']} chunk {c['chunk_index']}]\n{c['chunk_text']}"
            for c in chunks
        ])

        return f"""You are an expert evaluator for RAG systems.

Your task is to evaluate whether the given ANSWER is faithful to the CONTEXT.
A faithful answer only contains information that is present in the context.
An unfaithful answer contains information not found in the context (hallucination).

CONTEXT:
{context}

ANSWER:
{answer}

Score the faithfulness from 0.0 to 1.0 where:
1.0 = answer is completely grounded in the context
0.5 = answer is partially grounded, some information not in context
0.0 = answer is completely hallucinated or not grounded in context

Respond with ONLY a number between 0.0 and 1.0.
Score:"""

    def build_relevance_prompt(
        self,
        query: str,
        chunks: list[dict],
    ) -> str:
        """
        Asks the judge: did we retrieve the right chunks?
        Score 1.0 = perfect retrieval, 0.0 = completely irrelevant.
        """
        context = "\n\n".join([
            f"[Source: {c['file_name']} chunk {c['chunk_index']}]\n{c['chunk_text']}"
            for c in chunks
        ])

        return f"""You are an expert evaluator for RAG systems.

Your task is to evaluate whether the retrieved CONTEXT is relevant to the QUERY.
Relevant context contains information that would help answer the query.

QUERY:
{query}

RETRIEVED CONTEXT:
{context}

Score the relevance from 0.0 to 1.0 where:
1.0 = context is perfectly relevant and contains the answer
0.5 = context is partially relevant
0.0 = context is completely irrelevant to the query

Respond with ONLY a number between 0.0 and 1.0.
Score:"""

    def parse_score(self, response: str) -> float:
        """
        Extract a float score from the LLM response.
        Handles various response formats robustly.
        """
        if not response:
            return 0.0

        # Find all numbers in the response
        matches = re.findall(r"\d+\.?\d*", response)
        if not matches:
            return 0.0

        try:
            score = float(matches[0])
            # Clamp to 0.0 - 1.0
            return max(0.0, min(1.0, score))
        except ValueError:
            return 0.0

    async def evaluate(
        self,
        query: str,
        chunks: list[dict],
        answer: str,
    ) -> dict:
        """
        Run faithfulness and relevance evaluation.
        Returns scores between 0.0 and 1.0 for each dimension.
        """
        # Empty answer — no need to call judge
        if not answer.strip():
            return {
                "query": query,
                "faithfulness": 0.0,
                "relevance": 0.0,
                "chunks_evaluated": len(chunks),
            }

        # Empty chunks — no retrieval to evaluate
        if not chunks:
            return {
                "query": query,
                "faithfulness": 0.0,
                "relevance": 0.0,
                "chunks_evaluated": 0,
            }

        client = ollama.AsyncClient(host=self.base_url)

        # 1. Faithfulness score
        faithfulness_prompt = self.build_faithfulness_prompt(
            answer=answer,
            chunks=chunks,
        )
        faithfulness_response = await client.chat(
            model=self.judge_model,
            messages=[{"role": "user", "content": faithfulness_prompt}],
        )
        faithfulness = self.parse_score(
            faithfulness_response.message.content
        )

        # 2. Relevance score
        relevance_prompt = self.build_relevance_prompt(
            query=query,
            chunks=chunks,
        )
        relevance_response = await client.chat(
            model=self.judge_model,
            messages=[{"role": "user", "content": relevance_prompt}],
        )
        relevance = self.parse_score(
            relevance_response.message.content
        )

        return {
            "query": query,
            "faithfulness": faithfulness,
            "relevance": relevance,
            "chunks_evaluated": len(chunks),
        }