from typing import AsyncGenerator

from app.core.llm.base import BaseLLM, BaseEmbedder


class MistralLLM(BaseLLM):
    """
    Mistral AI generation provider.
    European servers — GDPR compliant.
    Best choice for EU law firm or finance clients.

    Models: mistral-large-latest, mistral-small-latest,
            open-mistral-nemo, codestral-latest
    """

    def __init__(self, api_key: str, model: str):
        try:
            from mistralai import Mistral
            self._client = Mistral(api_key=api_key)
        except ImportError:
            raise ImportError(
                "mistralai required. Install with: uv add mistralai"
            )
        self.model = model

    async def stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        # No await — stream_async returns async generator directly
        response = self._client.chat.stream_async(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        async for event in response:
            token = event.data.choices[0].delta.content
            if token:
                yield token
    async def complete(
        self,
        prompt: str,
    ) -> str:
        response = await self._client.chat.complete_async(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""


class MistralEmbedder(BaseEmbedder):
    """
    Mistral AI embedding provider.
    mistral-embed: 1024 dims, $0.10/M tokens.
    EU servers — important for GDPR-sensitive deployments.

    Note: Mistral uses 'inputs' not 'input' for batch embedding.
    """

    def __init__(self, api_key: str, model: str = "mistral-embed"):
        try:
            from mistralai import Mistral
            self._client = Mistral(api_key=api_key)
        except ImportError:
            raise ImportError(
                "mistralai required. Install with: uv add mistralai"
            )
        self.model = model

    async def embed_text(
        self,
        text: str,
    ) -> list[float]:
        response = await self._client.embeddings.create_async(
            model=self.model,
            inputs=[text],
        )
        return response.data[0].embedding

    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        # Mistral supports native batch — one API call
        response = await self._client.embeddings.create_async(
            model=self.model,
            inputs=texts,
        )
        return [d.embedding for d in response.data]