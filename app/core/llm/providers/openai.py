from typing import AsyncGenerator

from app.core.llm.base import BaseLLM, BaseEmbedder
from app.features.usage.recorder import estimate_tokens, record

# OpenAI-compatible providers — same API, different base_url
OPENAI_COMPATIBLE_PROVIDERS = {
    "openai": {
        "base_url": None,  # uses OpenAI default
        "supports_embeddings": True,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "supports_embeddings": True,  # nomic-embed-text-v1_5
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "supports_embeddings": False,
    },
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "supports_embeddings": False,
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "supports_embeddings": False,  # Mistral uses own SDK for embeddings
    },
}


class OpenAICompatibleLLM(BaseLLM):
    """
    Generation provider for all OpenAI-compatible APIs.
    Covers: OpenAI, Groq, DeepSeek, Grok (xAI), Mistral.

    All of these share the same API format — only base_url
    and api_key differ. This is your existing pattern applied
    to async streaming.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        provider: str = "openai",
        base_url: str | None = None,
    ):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package required. Install with: uv add openai"
            )

        # Use provided base_url or look up from provider map
        resolved_url = base_url or OPENAI_COMPATIBLE_PROVIDERS.get(
            provider, {}
        ).get("base_url")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=resolved_url,
        )
        self.model = model
        self.provider = provider
        self.kind = "chat"

    async def stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        # No await — stream=True returns async generator directly
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            stream_options={"include_usage": True},
            temperature=0.1,
        )
        used = None
        async for chunk in response:
            if getattr(chunk, "usage", None):
                used = chunk.usage
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        if used:
            await record(self.kind, self.provider, self.model, used.prompt_tokens, used.completion_tokens)

    async def complete(
        self,
        prompt: str,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            temperature=0.1,
        )
        text = response.choices[0].message.content or ""
        if response.usage:
            await record(self.kind, self.provider, self.model, response.usage.prompt_tokens, response.usage.completion_tokens)
        else:
            await record(self.kind, self.provider, self.model, estimate_tokens(prompt), estimate_tokens(text), estimated=True)
        return text


class OpenAIEmbedder(BaseEmbedder):
    """
    Embedding provider for OpenAI and Groq.

    OpenAI: text-embedding-3-small (1536 dims)
            text-embedding-3-large (3072 dims)
    Groq:   nomic-embed-text-v1_5  (768 dims)

    DeepSeek and Grok do not support embeddings —
    use a different embed provider with those generators.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        provider: str = "openai",
        base_url: str | None = None,
    ):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package required. Install with: uv add openai"
            )

        resolved_url = base_url or OPENAI_COMPATIBLE_PROVIDERS.get(
            provider, {}
        ).get("base_url")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=resolved_url,
        )
        self.model = model
        self.provider = provider
        self.kind = "embed"

    async def embed_text(
        self,
        text: str,
    ) -> list[float]:
        response = await self.client.embeddings.create(
            input=text,
            model=self.model,
        )
        await self._record(response, [text])
        return response.data[0].embedding

    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        # OpenAI accepts list natively — one API call
        response = await self.client.embeddings.create(
            input=texts,
            model=self.model,
        )
        await self._record(response, texts)
        # Sort by index to preserve order
        return [d.embedding for d in sorted(response.data, key=lambda x: x.index)]

    async def _record(self, response, texts: list[str]) -> None:
        if getattr(response, "usage", None):
            await record("embed", self.provider, self.model, response.usage.prompt_tokens)
        else:
            await record("embed", self.provider, self.model, sum(estimate_tokens(t) for t in texts), estimated=True)
