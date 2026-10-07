from typing import AsyncGenerator

import ollama

from app.core.llm.base import BaseLLM, BaseEmbedder
from app.features.usage.recorder import estimate_tokens, record


class OllamaLLM(BaseLLM):
    def __init__(self, base_url: str, model: str, api_key: str = ""):
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = ollama.AsyncClient(host=base_url, headers=headers)
        self.model = model
        self.kind = "chat"

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
        used_in = used_out = None
        async for chunk in response:
            if chunk.done:
                used_in, used_out = chunk.prompt_eval_count, chunk.eval_count
            token = chunk.message.content
            if token:
                yield token
        if used_in is not None:
            await record(self.kind, "ollama", self.model, used_in, used_out or 0)
        else:
            await record(self.kind, "ollama", self.model, estimate_tokens(prompt), 0, estimated=True)

    async def complete(
        self,
        prompt: str,
    ) -> str:
        # No stream=False needed — default is non-streaming
        response = await self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.message.content or ""
        if response.prompt_eval_count is not None:
            await record(self.kind, "ollama", self.model, response.prompt_eval_count, response.eval_count or 0)
        else:
            await record(self.kind, "ollama", self.model, estimate_tokens(prompt), estimate_tokens(text), estimated=True)
        return text


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