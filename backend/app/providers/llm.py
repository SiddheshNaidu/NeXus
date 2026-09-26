"""Google Gemini LLM provider — Sprint 4/5.

Uses the `google-genai` SDK (google.genai) to call `gemini-2.0-flash-lite`
(configured via settings.llm_model) asynchronously using `run_in_executor`,
mirroring the pattern from the embedding provider in Sprint 3.

Sprint 5 adds `stream_complete()` — an async generator that yields text chunks
as they arrive from the model using `generate_content_stream`.

Usage:
    from app.providers.llm import GeminiLLMProvider
    provider = GeminiLLMProvider()
    text = await provider.complete([
        {"role": "user", "content": "What is the capital of France?"}
    ])
    async for chunk in provider.stream_complete([...]):
        print(chunk, end="", flush=True)
"""
import asyncio
from collections.abc import AsyncIterator
from typing import Any

from google import genai as _genai
from google.genai import types as _types

from app.core.config import settings
from app.providers import LLMProvider

# Singleton client — shared with embeddings if the same API key is used.
_client = _genai.Client(api_key=settings.llm_api_key)


class GeminiLLMProvider(LLMProvider):
    """Concrete LLM provider backed by Google Gemini Flash."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or settings.llm_model

    def _build_gemini_args(
        self, messages: list[dict], **kwargs
    ) -> tuple[list[_types.ContentUnion], _types.GenerateContentConfig]:
        """Shared helper: convert messages → (chat_messages, config)."""
        system_instruction = None
        chat_messages: list[_types.ContentUnion] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            else:
                gemini_role = "model" if role == "assistant" else "user"
                chat_messages.append(
                    _types.Content(
                        role=gemini_role,
                        parts=[_types.Part(text=content)],
                    )
                )

        config = _types.GenerateContentConfig(
            temperature=kwargs.get("temperature", 0.2),
            max_output_tokens=kwargs.get("max_tokens", 2048),
        )
        if system_instruction:
            config.system_instruction = system_instruction

        return chat_messages, config

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Send a chat-completion request and return the model's text reply.

        *messages* is a list of dicts with keys ``role`` and ``content``.
        The first message with role ``"system"`` is converted to a system
        instruction; all others become the conversation history.
        """
        loop = asyncio.get_event_loop()
        chat_messages, config = self._build_gemini_args(messages, **kwargs)

        def _call() -> str:
            response = _client.models.generate_content(
                model=self._model,
                contents=chat_messages,
                config=config,
            )
            return response.text or ""

        return await loop.run_in_executor(None, _call)

    async def stream_complete(
        self, messages: list[dict], **kwargs
    ) -> AsyncIterator[str]:
        """Stream text chunks from the model as an async generator.

        Each yielded value is a non-empty string token/chunk.
        Uses generate_content_stream (synchronous SDK call) executed in a
        thread pool so the event loop remains unblocked.
        """
        loop = asyncio.get_event_loop()
        chat_messages, config = self._build_gemini_args(messages, **kwargs)

        # Collect all chunks via the synchronous streaming API in a thread,
        # then yield them one by one.  A true async-native alternative would
        # require the async SDK client, but run_in_executor is sufficient here
        # and keeps the event loop free during I/O.
        import queue as _queue
        import threading as _threading

        chunk_queue: _queue.Queue[str | None] = _queue.Queue()

        def _stream() -> None:
            try:
                for chunk in _client.models.generate_content_stream(
                    model=self._model,
                    contents=chat_messages,
                    config=config,
                ):
                    text = chunk.text
                    if text:
                        chunk_queue.put(text)
            finally:
                chunk_queue.put(None)  # sentinel

        thread = _threading.Thread(target=_stream, daemon=True)
        thread.start()

        while True:
            # Poll the queue without blocking the event loop
            item = await loop.run_in_executor(None, chunk_queue.get)
            if item is None:
                break
            yield item

    async def complete_structured(
        self, messages: list[dict], schema: type, **kwargs
    ) -> dict:
        """Send a chat-completion request and return a validated structured dict.

        Delegates to complete() and parses the returned JSON text.
        Sprint 4 does not use structured output — this satisfies the ABC contract.
        """
        import json

        text = await self.complete(messages, **kwargs)
        # Strip markdown code fences if the model wraps output
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1]) if len(lines) > 2 else stripped
        return json.loads(stripped)


# Module-level singleton
_provider: GeminiLLMProvider | None = None


def get_llm_provider() -> GeminiLLMProvider:
    """Return the module-level singleton LLM provider (created lazily)."""
    global _provider
    if _provider is None:
        _provider = GeminiLLMProvider()
    return _provider
