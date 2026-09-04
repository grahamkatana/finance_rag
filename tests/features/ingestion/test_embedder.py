import math
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.features.ingestion.embedder import Embedder


class FakeEmbedder:
    """Deterministic in-memory embedder used to decouple tests from Ollama/network."""

    def __init__(self, size: int):
        self.size = size

    def _word_vector(self, word: str) -> list[float]:
        # Consistent deterministic direction per word so shared words
        # contribute to cosine similarity.
        seed = sum(ord(c) * (i + 1) for i, c in enumerate(word))
        rng_state = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        raw = []
        for _ in range(self.size):
            rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
            raw.append((rng_state / 0x7FFFFFFF) - 0.5)
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]

    def _vector(self, text: str) -> list[float]:
        # Bag-of-words: sum per-word vectors then renormalize. Texts sharing
        # words land close together in the space.
        words = "".join(c.lower() if c.isalnum() else " " for c in text).split()
        acc = [0.0] * self.size
        for word in words:
            w = self._word_vector(word)
            for i in range(self.size):
                acc[i] += w[i]
        norm = math.sqrt(sum(v * v for v in acc)) or 1.0
        return [v / norm for v in acc]

    async def embed_text(self, text: str) -> list[float]:
        return self._vector(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]


@pytest.fixture
def embedder():
    with patch(
        "app.features.ingestion.embedder.get_embedder",
        return_value=FakeEmbedder(settings.embedding_size),
    ):
        yield Embedder()


@pytest.mark.asyncio
async def test_embed_single_text_returns_vector(embedder):
    """Single text should return a list of floats"""
    vector = await embedder.embed_text("Apple revenue grew 12% in Q3.")
    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(v, float) for v in vector)


@pytest.mark.asyncio
async def test_embed_returns_correct_dimensions(embedder):
    """Embedding dimensions must match config EMBEDDING_SIZE"""
    vector = await embedder.embed_text("Apple revenue grew 12% in Q3.")
    assert len(vector) == settings.embedding_size


@pytest.mark.asyncio
async def test_embed_batch_returns_multiple_vectors(embedder):
    """Batch embed should return one vector per text"""
    texts = [
        "Apple revenue grew 12% in Q3.",
        "Tesla reported record deliveries.",
        "Microsoft cloud division up 21%.",
    ]
    vectors = await embedder.embed_batch(texts)
    assert len(vectors) == len(texts)


@pytest.mark.asyncio
async def test_embed_batch_all_correct_dimensions(embedder):
    """Every vector in batch must match config EMBEDDING_SIZE"""
    texts = [
        "Apple revenue grew 12% in Q3.",
        "Tesla reported record deliveries.",
    ]
    vectors = await embedder.embed_batch(texts)
    assert all(len(v) == settings.embedding_size for v in vectors)


@pytest.mark.asyncio
async def test_similar_texts_produce_similar_vectors(embedder):
    """
    Semantically similar texts should have high cosine similarity.
    """
    v1 = await embedder.embed_text("Apple quarterly revenue report.")
    v2 = await embedder.embed_text("Apple earnings for the quarter.")
    v3 = await embedder.embed_text("The weather is sunny today.")

    def cosine_similarity(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x ** 2 for x in a))
        mag_b = math.sqrt(sum(x ** 2 for x in b))
        return dot / (mag_a * mag_b)

    similar_score = cosine_similarity(v1, v2)
    different_score = cosine_similarity(v1, v3)

    assert similar_score > different_score
