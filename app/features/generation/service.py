from typing import AsyncGenerator

from app.core.config import settings
from app.core.llm.connector import get_llm
from app.core.prompts.helpers import build_generation_prompt


class GenerationService:
    def __init__(self):
        self.llm = get_llm(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    async def stream(
        self,
        query: str,
        chunks: list[dict],
    ) -> AsyncGenerator[str, None]:
        prompt = build_generation_prompt(query=query, chunks=chunks)
        async for token in self.llm.stream(prompt):
            yield token