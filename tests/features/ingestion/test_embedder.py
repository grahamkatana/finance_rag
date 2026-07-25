import pytest
from app.features.ingestion.embedder import Embedder


@pytest.fixture
def embedder():
    return Embedder()


@pytest.mark.asyncio
async def test_embed_single_text_returns_vector(embedder):
    """Single text should return a list of floats"""
    vector = await embedder.embed_text("Apple revenue grew 12% in Q3.")
    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(v, float) for v in vector)


@pytest.mark.asyncio
async def test_embed_returns_correct_dimensions(embedder):
    """nomic-embed-text always returns 768 dimensions"""
    vector = await embedder.embed_text("Apple revenue grew 12% in Q3.")
    assert len(vector) == 768


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
    """Every vector in batch must be 768 dimensions"""
    texts = [
        "Apple revenue grew 12% in Q3.",
        "Tesla reported record deliveries.",
    ]
    vectors = await embedder.embed_batch(texts)
    assert all(len(v) == 768 for v in vectors)


@pytest.mark.asyncio
async def test_similar_texts_produce_similar_vectors(embedder):
    """
    Semantically similar texts should have high cosine similarity.
    This confirms the embedding model is working meaningfully.
    """
    import math

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

    # Similar financial texts should score higher than unrelated text
    assert similar_score > different_score