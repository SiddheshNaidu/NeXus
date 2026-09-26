"""Provider interfaces — stub definitions locked in Sprint 0.

Real implementations are wired in Sprint 3 (AI/Retrieval).
Sprint 5 adds stream_complete() to LLMProvider.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class EmbeddingProvider(ABC):
    """Abstract interface for embedding generation."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return a list of embedding vectors, one per input text."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors produced by this provider."""
        ...


class LLMProvider(ABC):
    """Abstract interface for language model generation."""

    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Send a chat-completion request and return the model's text reply."""
        ...

    @abstractmethod
    async def complete_structured(self, messages: list[dict], schema: type, **kwargs) -> dict:
        """Send a chat-completion request and return a validated structured dict."""
        ...

    async def stream_complete(
        self, messages: list[dict], **kwargs
    ) -> AsyncIterator[str]:
        """Stream text chunks as an async generator.

        Default implementation delegates to complete() and yields the full
        response as a single chunk.  Concrete providers may override this.
        """
        text = await self.complete(messages, **kwargs)
        yield text
