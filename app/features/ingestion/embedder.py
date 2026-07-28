from app.core.config import settings
from app.core.llm.connector import get_embedder
from app.core.llm.base import BaseEmbedder


class Embedder:
    """
    Thin wrapper around the embedder connector.
    Reads provider config from settings at instantiation.
    Swap embed provider by changing EMBED_PROVIDER in .env.
    """

    def __init__(self):
        self._embedder: BaseEmbedder = get_embedder(
            provider=settings.embed_provider,
            model=settings.embed_model,
            api_key=settings.embed_api_key,
            base_url=settings.embed_base_url,
        )

    async def embed_text(self, text: str) -> list[float]:
        return await self._embedder.embed_text(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return await self._embedder.embed_batch(texts)