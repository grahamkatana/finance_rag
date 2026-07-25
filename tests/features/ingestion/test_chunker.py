import pytest
from app.features.ingestion.chunker import Chunk, Chunker


@pytest.fixture
def chunker():
    return Chunker(chunk_size=512, chunk_overlap=64)


def test_chunker_returns_chunks(chunker):
    """Basic sanity — text should produce at least one chunk"""
    text = "This is a test sentence. " * 50
    chunks = chunker.chunk(text)
    assert len(chunks) > 0


def test_chunks_are_correct_type(chunker):
    """Every item returned must be a Chunk dataclass"""
    text = "This is a test sentence. " * 50
    chunks = chunker.chunk(text)
    assert all(isinstance(c, Chunk) for c in chunks)


def test_chunk_index_is_sequential(chunker):
    """Chunks must be numbered 0, 1, 2... in order"""
    text = "This is a test sentence. " * 50
    chunks = chunker.chunk(text)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_chunk_overlap(chunker):
    """
    Each chunk should start before the previous one ended.
    This confirms overlap is working.
    """
    text = "This is a test sentence. " * 50
    chunks = chunker.chunk(text)
    for i in range(1, len(chunks)):
        assert chunks[i].char_start < chunks[i - 1].char_end


def test_no_empty_chunks(chunker):
    """Empty chunks must never make it through"""
    text = "This is a test sentence. " * 50
    chunks = chunker.chunk(text)
    assert all(len(c.text.strip()) > 0 for c in chunks)


def test_short_text_produces_single_chunk(chunker):
    """Text shorter than chunk_size should be one chunk"""
    text = "Short text."
    chunks = chunker.chunk(text)
    assert len(chunks) == 1


def test_clean_removes_excessive_newlines(chunker):
    """PDF noise — multiple newlines should be collapsed"""
    text = "First paragraph.\n\n\n\n\nSecond paragraph."
    chunks = chunker.chunk(text)
    assert "\n\n\n" not in chunks[0].text


def test_chunk_text_matches_original_position(chunker):
    """char_start and char_end should correctly slice original text"""
    text = "This is a test sentence. " * 50
    cleaned = chunker._clean(text)
    chunks = chunker.chunk(text)
    for chunk in chunks:
        sliced = cleaned[chunk.char_start:chunk.char_end].strip()
        assert sliced == chunk.text