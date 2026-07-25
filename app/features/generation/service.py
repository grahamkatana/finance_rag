from typing import AsyncGenerator

import ollama

from app.core.config import settings


class GenerationService:
    def __init__(self):
        self.model = settings.ollama_llm_model
        self.base_url = settings.ollama_base_url

    def build_prompt(
        self,
        query: str,
        chunks: list[dict],
    ) -> str:
        if not chunks:
            return f"""You are a financial analyst assistant.
You have no context available for this query.
Politely tell the user you could not find relevant information.

Question: {query}

Answer:"""

        context_parts = []
        for i, chunk in enumerate(chunks, start=1):
            context_parts.append(
                f"[Source {i}: {chunk['file_name']} chunk {chunk['chunk_index']}]\n"
                f"{chunk['chunk_text']}"
            )
        context = "\n\n".join(context_parts)

        return f"""You are a financial analyst assistant.
Answer the question using ONLY the context provided below.

Important instructions:
- The context may contain financial tables where numbers appear in columns representing different fiscal years.
- For Apple 10-K filings the columns are always in this order: 2024, 2023, 2022 (left to right).
- When you see a row like "Total net sales 391,035 383,285 394,328" it means: 2024=$391,035M, 2023=$383,285M, 2022=$394,328M.
- Numbers are in millions of dollars unless stated otherwise.
- If the answer is not in the context say "I could not find that information in the provided documents."
- Do not make up numbers, dates, or facts.
- Always cite which source you used by mentioning the source number.

Context:
{context}

Question: {query}

Answer:"""

    async def stream(
        self,
        query: str,
        chunks: list[dict],
    ) -> AsyncGenerator[str, None]:
        prompt = self.build_prompt(query=query, chunks=chunks)

        client = ollama.AsyncClient(host=self.base_url)

        response = await client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )

        async for chunk in response:
            token = chunk.message.content
            if token:
                yield token