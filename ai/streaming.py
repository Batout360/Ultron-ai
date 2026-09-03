"""
ULTRON Streaming Response Buffer
Buffers streaming LLM tokens and emits sentence-level chunks to TTS.
This is the core of the "hear the response while it's still generating" feature.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import AsyncGenerator, Callable, Optional

logger = logging.getLogger(__name__)

# Sentence boundary patterns
SENTENCE_END = re.compile(r'([.!?][\s"\')\]]*(?:\s|$))')
# Chunk also at colons/semicolons when buffer is long enough
CLAUSE_END = re.compile(r'([;:])\s')

# Minimum chars before emitting a chunk (avoids very short TTS calls)
MIN_CHUNK_CHARS = 40
# Maximum chars before forcing a flush (avoids long silent periods)
MAX_CHUNK_CHARS = 300


class StreamingBuffer:
    """
    Buffers incoming text tokens and emits complete sentences for TTS.

    Usage:
        buf = StreamingBuffer(on_chunk=my_tts_func)
        async for token in llm.stream(...):
            await buf.feed(token)
        await buf.flush()  # Send any remaining text
    """

    def __init__(
        self,
        on_chunk: Optional[Callable[[str], None]] = None,
        min_chars: int = MIN_CHUNK_CHARS,
        max_chars: int = MAX_CHUNK_CHARS,
    ) -> None:
        self._buffer = ""
        self._on_chunk = on_chunk
        self._min_chars = min_chars
        self._max_chars = max_chars
        self._chunks_emitted: list[str] = []
        self._total_chars = 0

    async def feed(self, token: str) -> None:
        """Feed a new token into the buffer. May emit a chunk."""
        self._buffer += token
        self._total_chars += len(token)
        await self._try_emit()

    async def _try_emit(self) -> None:
        """Check if we should emit a chunk to TTS."""
        if len(self._buffer) < self._min_chars:
            return

        # Try sentence boundary
        match = SENTENCE_END.search(self._buffer)
        if match:
            end_pos = match.end()
            chunk = self._buffer[:end_pos].strip()
            self._buffer = self._buffer[end_pos:]
            if chunk:
                await self._emit(chunk)
            return

        # Force flush if too long
        if len(self._buffer) >= self._max_chars:
            # Find last word boundary
            last_space = self._buffer.rfind(" ", 0, self._max_chars)
            if last_space > self._min_chars:
                chunk = self._buffer[:last_space].strip()
                self._buffer = self._buffer[last_space:].lstrip()
                if chunk:
                    await self._emit(chunk)

    async def flush(self) -> None:
        """Emit any remaining buffered text."""
        if self._buffer.strip():
            await self._emit(self._buffer.strip())
            self._buffer = ""

    async def _emit(self, text: str) -> None:
        """Emit a chunk to the TTS callback."""
        if not text:
            return
        self._chunks_emitted.append(text)
        logger.debug("TTS chunk: %s...", text[:60])
        if self._on_chunk:
            result = self._on_chunk(text)
            if asyncio.iscoroutine(result):
                await result

    def clear(self) -> None:
        """Discard all buffered content (e.g., on interrupt)."""
        self._buffer = ""

    @property
    def chunks_emitted(self) -> list[str]:
        return list(self._chunks_emitted)

    @property
    def total_chars(self) -> int:
        return self._total_chars


class TokenAccumulator:
    """
    Simpler accumulator for collecting the full response text
    while simultaneously streaming to UI/TTS.
    """

    def __init__(self) -> None:
        self._tokens: list[str] = []

    def add(self, token: str) -> None:
        self._tokens.append(token)

    @property
    def text(self) -> str:
        return "".join(self._tokens)

    @property
    def token_count(self) -> int:
        return len(self._tokens)

    def clear(self) -> None:
        self._tokens.clear()


def split_into_sentences(text: str) -> list[str]:
    """
    Split a block of text into individual sentences.
    Used for replaying/re-processing completed responses.
    """
    if not text:
        return []

    sentences = []
    current = ""

    for i, char in enumerate(text):
        current += char
        if char in ".!?" and i + 1 < len(text):
            next_char = text[i + 1]
            if next_char in " \n\t\"'":
                s = current.strip()
                if s:
                    sentences.append(s)
                current = ""

    if current.strip():
        sentences.append(current.strip())

    return sentences


def estimate_tokens(text: str) -> int:
    """
    Quick estimate of token count from text.
    Rough approximation: ~4 chars per token for English.
    """
    return max(1, len(text) // 4)
