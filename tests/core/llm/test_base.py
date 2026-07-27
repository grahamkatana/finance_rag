import pytest
from app.core.llm.base import BaseLLM, BaseEmbedder


def test_base_llm_cannot_be_instantiated():
    """BaseLLM is abstract — cannot instantiate directly"""
    with pytest.raises(TypeError):
        BaseLLM()  # type: ignore


def test_base_embedder_cannot_be_instantiated():
    """BaseEmbedder is abstract — cannot instantiate directly"""
    with pytest.raises(TypeError):
        BaseEmbedder()  # type: ignore


def test_concrete_llm_must_implement_stream():
    """A concrete LLM missing stream() cannot be instantiated"""
    class IncompleteLLM(BaseLLM):
        async def complete(self, prompt: str) -> str:
            return ""
        # missing stream()

    with pytest.raises(TypeError):
        IncompleteLLM()  # type: ignore


def test_concrete_llm_must_implement_complete():
    """A concrete LLM missing complete() cannot be instantiated"""
    class IncompleteLLM(BaseLLM):
        async def stream(self, prompt: str):
            yield ""
        # missing complete()

    with pytest.raises(TypeError):
        IncompleteLLM()  # type: ignore


def test_concrete_embedder_must_implement_both_methods():
    """A concrete embedder missing embed_batch() cannot be instantiated"""
    class IncompleteEmbedder(BaseEmbedder):
        async def embed_text(self, text: str) -> list[float]:
            return []
        # missing embed_batch()

    with pytest.raises(TypeError):
        IncompleteEmbedder()  # type: ignore


def test_valid_llm_implementation_instantiates():
    """A complete LLM implementation should instantiate fine"""
    class ValidLLM(BaseLLM):
        async def stream(self, prompt: str):
            yield "token"

        async def complete(self, prompt: str) -> str:
            return "response"

    llm = ValidLLM()
    assert llm is not None


def test_valid_embedder_implementation_instantiates():
    """A complete embedder implementation should instantiate fine"""
    class ValidEmbedder(BaseEmbedder):
        async def embed_text(self, text: str) -> list[float]:
            return [0.1, 0.2]

        async def embed_batch(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2] for _ in texts]

    embedder = ValidEmbedder()
    assert embedder is not None