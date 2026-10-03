from app.core.config import settings
from app.core.llm.connector import get_embedder
from app.core.llm.base import BaseEmbedder

# Safe per-request ceiling: Voyage caps at 128 docs / 32K tokens per call,
# OpenAI at 2048 inputs. 64 keeps every provider comfortably under its limit.
DEFAULT_BATCH_SIZE = 64


class Embedder:
    """
    Thin wrapper around the embedder connector.
    Reads provider config from settings at instantiation.
    Swap embed provider by changing EMBED_PROVIDER in .env.

    embed_batch() chunks the input into sub-batches so a single large
    ingestion can't overflow the provider's per-request limit (or blow
    past free-tier rate limits in one giant call).
    """

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE):
        self._embedder: BaseEmbedder = get_embedder(
            provider=settings.embed_provider,
            model=settings.embed_model,
            api_key=settings.embed_api_key,
            base_url=settings.embed_base_url,
        )
        self.batch_size = batch_size

    async def embed_text(self, text: str) -> list[float]:
        return await self._embedder.embed_text(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            vectors.extend(await self._embedder.embed_batch(chunk))
        return vectors