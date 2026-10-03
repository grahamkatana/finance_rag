from typing import AsyncGenerator

import ollama

from app.core.llm.base import BaseLLM, BaseEmbedder


class OllamaLLM(BaseLLM):
    def __init__(self, base_url: str, model: str, api_key: str = ""):
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = ollama.AsyncClient(host=base_url, headers=headers)
        self.model = model

    async def stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        # await first — chat() is a coroutine that resolves to the async generator
        response = await self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in response:
            token = chunk.message.content
            if token:
                yield token

    async def complete(
        self,
        prompt: str,
    ) -> str:
        # No stream=False needed — default is non-streaming
        response = await self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.message.content or ""


class OllamaEmbedder(BaseEmbedder):
    def __init__(self, base_url: str, model: str, api_key: str = ""):
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = ollama.AsyncClient(host=base_url, headers=headers)
        self.model = model

    async def embed_text(
        self,
        text: str,
    ) -> list[float]:
        response = await self.client.embed(
            model=self.model,
            input=text,
        )
        return response.embeddings[0]

    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        response = await self.client.embed(
            model=self.model,
            input=texts,
        )
        return response.embeddings