from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseLLM(ABC):
    """
    Abstract interface for all generation providers.
    Every provider must implement stream() and complete().

    stream()    → used by generation router (real-time tokens)
    complete()  → used by eval judge (single response)
    """

    @abstractmethod
    async def stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens one by one as they are generated.
        Used for real-time RAG answers.
        """
        ...

    @abstractmethod
    async def complete(
        self,
        prompt: str,
    ) -> str:
        """
        Return full response in one call.
        Used by eval judge — no streaming needed.
        """
        ...


class BaseEmbedder(ABC):
    """
    Abstract interface for all embedding providers.
    Every provider must implement embed_text() and embed_batch().

    embed_text()  → single query embedding at search time
    embed_batch() → bulk embedding at ingestion time
    """

    @abstractmethod
    async def embed_text(
        self,
        text: str,
    ) -> list[float]:
        """
        Embed a single string into a vector.
        Called at query time — must be fast.
        """
        ...

    @abstractmethod
    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Embed multiple strings in one call.
        Called at ingestion time — must be efficient.
        Providers that don't support native batching
        should loop internally rather than exposing
        that detail to callers.
        """
        ...