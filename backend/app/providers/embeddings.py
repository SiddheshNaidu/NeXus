"""Google Gemini embedding provider — Sprint 3.

Uses the `google-genai` SDK (google.genai) to call the `gemini-embedding-2`
model asynchronously.  The API key is read from settings.embedding_api_key
(EMBEDDING_API_KEY in .env).

Usage:
    from app.providers.embeddings import GeminiEmbeddingProvider
    provider = GeminiEmbeddingProvider()
    vectors = await provider.embed(["text one", "text two"])
"""
import asyncio
import logging

from google import genai as _genai
from google.genai import types as _types

from app.core.config import settings
from app.providers import EmbeddingProvider

logger = logging.getLogger(__name__)

# Singleton client — created once at import time.
# The google-genai client is thread-safe and reusable.
_client = _genai.Client(api_key=settings.embedding_api_key)

# Maximum texts Google allows in a single embed_content call.
_BATCH_SIZE = 100

# Retry configuration for individual embedding batches.
# On rate-limit (429) or transient network errors, the batch is retried with
# exponential back-off before being logged and skipped (DLQ behaviour).
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0   # seconds
_RETRY_BACKOFF = 2.0      # multiplier per attempt


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Concrete embedding provider backed by Google Gemini embedding-2."""

    def __init__(
        self,
        model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self._model = model or settings.embedding_model
        self._dimension = dimension or settings.embedding_dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed *texts* and return one vector per input.

        Splits into batches of up to _BATCH_SIZE to stay within API limits.
        All batch calls run concurrently via asyncio.gather.
        """
        if not texts:
            return []

        batches = [
            texts[i : i + _BATCH_SIZE]
            for i in range(0, len(texts), _BATCH_SIZE)
        ]

        batch_results = await asyncio.gather(
            *[self._embed_batch(batch) for batch in batches]
        )

        # Flatten list of lists
        return [vec for batch in batch_results for vec in batch]

    async def _embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Call the Gemini embedding API for a single batch asynchronously.

        Retries up to _MAX_RETRIES times with exponential back-off on any
        exception (rate-limit, network timeout, etc.).  If all retries are
        exhausted the batch is logged and a list of *None* placeholders is
        returned — this is the Dead Letter Queue behaviour: successfully
        embedded batches are never discarded because one batch failed.
        """
        loop = asyncio.get_event_loop()
        delay = _RETRY_BASE_DELAY

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                def _call() -> list[list[float]]:
                    response = _client.models.embed_content(
                        model=self._model,
                        contents=texts,
                        config=_types.EmbedContentConfig(
                            output_dimensionality=self._dimension,
                            task_type="RETRIEVAL_DOCUMENT",
                        ),
                    )
                    return [emb.values for emb in response.embeddings]

                # run_in_executor keeps the async event loop unblocked while
                # the synchronous SDK call is in flight.
                return await loop.run_in_executor(None, _call)

            except Exception as exc:
                if attempt == _MAX_RETRIES:
                    logger.error(
                        "Embedding batch failed after %d attempts (%d texts): %s",
                        _MAX_RETRIES,
                        len(texts),
                        exc,
                    )
                    # Return None placeholders so the caller can skip these
                    # chunks while keeping all successfully embedded batches.
                    return [None] * len(texts)  # type: ignore[return-value]

                logger.warning(
                    "Embedding batch attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                delay *= _RETRY_BACKOFF


async def embed_query(text: str) -> list[float]:
    """Convenience helper: embed a single search query string.

    Uses RETRIEVAL_QUERY task type so the query vector is comparable to
    the RETRIEVAL_DOCUMENT vectors stored in the DB.
    """
    loop = asyncio.get_event_loop()

    def _call() -> list[float]:
        response = _client.models.embed_content(
            model=settings.embedding_model,
            contents=[text],
            config=_types.EmbedContentConfig(
                output_dimensionality=settings.embedding_dimension,
                task_type="RETRIEVAL_QUERY",
            ),
        )
        return response.embeddings[0].values

    return await loop.run_in_executor(None, _call)


# Module-level singleton for import convenience
_provider: GeminiEmbeddingProvider | None = None


def get_embedding_provider() -> GeminiEmbeddingProvider:
    """Return the module-level singleton provider (created lazily)."""
    global _provider
    if _provider is None:
        _provider = GeminiEmbeddingProvider()
    return _provider
