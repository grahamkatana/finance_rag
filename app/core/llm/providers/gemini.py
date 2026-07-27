from typing import AsyncGenerator

from app.core.llm.base import BaseLLM, BaseEmbedder


class GeminiLLM(BaseLLM):
    """
    Google Gemini generation provider.
    Uses native google-generativeai SDK — not OpenAI compatible.

    Models: gemini-2.0-flash, gemini-2.5-pro etc.
    """

    def __init__(self, api_key: str, model: str):
        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise ImportError(
                "google-generativeai required. Install with: uv add google-generativeai"
            )

        self._genai.configure(api_key=api_key)
        self.model = model

    async def stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        model = self._genai.GenerativeModel(self.model)
        # No await — streaming returns async generator directly
        response = model.generate_content_async(
            prompt,
            stream=True,
            generation_config=self._genai.GenerationConfig(temperature=0.1),
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    async def complete(
        self,
        prompt: str,
    ) -> str:
        model = self._genai.GenerativeModel(self.model)
        response = await model.generate_content_async(
            prompt,
            generation_config=self._genai.GenerationConfig(temperature=0.1),
        )
        return response.text or ""


class GeminiEmbedder(BaseEmbedder):
    """
    Google Gemini embedding provider.
    text-embedding-005 — best price/performance in 2026.
    $0.006/M tokens — 20x cheaper than OpenAI large.
    768 dimensions.
    """

    def __init__(self, api_key: str, model: str = "models/text-embedding-005"):
        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise ImportError(
                "google-generativeai required. Install with: uv add google-generativeai"
            )

        self._genai.configure(api_key=api_key)
        self.model = model

    async def embed_text(
        self,
        text: str,
    ) -> list[float]:
        import asyncio
        # Gemini embed is sync — run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._genai.embed_content(
                model=self.model,
                content=text,
            )
        )
        return result["embedding"]

    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        import asyncio
        loop = asyncio.get_event_loop()

        async def embed_one(text: str) -> list[float]:
            result = await loop.run_in_executor(
                None,
                lambda t=text: self._genai.embed_content(
                    model=self.model,
                    content=t,
                )
            )
            return result["embedding"]

        # Run all embeddings concurrently
        return list(await asyncio.gather(*[embed_one(t) for t in texts]))