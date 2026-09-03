"""
ULTRON LLM Provider
Abstract interface + concrete implementations for local LLM backends.

Supported backends:
  - GPT-OSS via Ollama (primary - already running on your machine)
  - Generic Ollama
  - LM Studio (OpenAI-compatible)
  - OpenAI-compatible (any server)
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

import httpx

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    tokens_used: int = 0
    model: str = ""
    done: bool = True
    tool_calls: list[dict] = None

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


@dataclass
class StreamChunk:
    """Single chunk from a streaming LLM response."""
    type: str           # "content" | "tool_call" | "done" | "error"
    content: str = ""
    name: str = ""      # tool name if type == "tool_call"
    arguments: dict = None
    error: str = ""

    def __post_init__(self):
        if self.arguments is None:
            self.arguments = {}


class LLMProvider(ABC):
    """Abstract base class for all LLM backends."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Non-streaming completion."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Streaming completion.
        Yields dicts: {"type": "content", "content": "..."} or {"type": "tool_call", ...}
        """
        ...

    @abstractmethod
    async def check_connection(self) -> bool:
        """Returns True if the backend is reachable."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources (close HTTP client etc.)."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


class OllamaProvider(LLMProvider):
    """
    Ollama backend - primary provider for GPT-OSS.
    Uses Ollama's /api/chat endpoint which supports streaming + tools.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.llm.endpoint.rstrip("/")
        self._model = settings.llm.model
        self._temperature = settings.llm.temperature
        self._max_tokens = settings.llm.max_tokens
        self._timeout = settings.llm.timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(
                    connect=5.0,
                    read=self._timeout,
                    write=10.0,
                    pool=5.0,
                ),
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
            )
        return self._client

    async def check_connection(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            client = self._get_client()
            response = await client.get("/api/tags", timeout=5.0)
            if response.status_code != 200:
                return False

            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            model_base = self._model.split(":")[0]

            available = any(
                self._model in m or model_base in m
                for m in models
            )
            if not available:
                logger.warning(
                    "Model '%s' not found in Ollama. Available: %s",
                    self._model, models
                )
            else:
                logger.info("Ollama: model '%s' is available", self._model)
            return True  # Ollama is running even if model not listed yet
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("Ollama connection failed: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error checking Ollama: %s", e)
            return False

    async def complete(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Non-streaming completion via /api/chat."""
        payload = self._build_payload(messages, tools, stream=False)
        try:
            client = self._get_client()
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

            message = data.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])

            return LLMResponse(
                content=content,
                tokens_used=data.get("eval_count", 0),
                model=data.get("model", self._model),
                done=data.get("done", True),
                tool_calls=self._parse_tool_calls(tool_calls),
            )
        except httpx.HTTPStatusError as e:
            logger.error("Ollama HTTP error: %s %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("Ollama completion error: %s", e)
            raise

    async def stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Streaming completion. Yields content chunks and tool calls.
        Each yielded dict has: {"type": "content", "content": "..."} or
                               {"type": "tool_call", "name": ..., "arguments": ...}
        """
        payload = self._build_payload(messages, tools, stream=True)
        tool_call_buffer: dict = {}

        try:
            client = self._get_client()
            async with client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    message = data.get("message", {})
                    content = message.get("content", "")
                    tool_calls = message.get("tool_calls", [])

                    if content:
                        yield {"type": "content", "content": content}

                    for tc in tool_calls:
                        function = tc.get("function", {})
                        name = function.get("name", "")
                        args = function.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        yield {"type": "tool_call", "name": name, "arguments": args}

                    if data.get("done", False):
                        break

        except httpx.ConnectError:
            logger.error("Lost connection to Ollama during streaming")
            yield {"type": "error", "content": "Connection to GPT-OSS lost"}
        except httpx.TimeoutException:
            logger.error("Ollama stream timeout")
            yield {"type": "error", "content": "GPT-OSS response timed out"}
        except Exception as e:
            logger.error("Ollama stream error: %s", e, exc_info=True)
            yield {"type": "error", "content": str(e)}

    def _build_payload(
        self,
        messages: list[dict],
        tools: Optional[list[dict]],
        stream: bool,
    ) -> dict:
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self._temperature,
                "num_predict": self._max_tokens,
                "num_ctx": self._settings.llm.context_size,
            },
        }
        if tools:
            payload["tools"] = tools
        return payload

    def _parse_tool_calls(self, raw: list) -> list[dict]:
        result = []
        for tc in raw:
            function = tc.get("function", {})
            result.append({
                "name": function.get("name", ""),
                "arguments": function.get("arguments", {}),
            })
        return result

    @property
    def model_name(self) -> str:
        return self._model

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class OpenAICompatibleProvider(LLMProvider):
    """
    Provider for any OpenAI-compatible local server (LM Studio, llama.cpp server, etc.)
    Uses /v1/chat/completions endpoint.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.llm.endpoint.rstrip("/")
        self._model = settings.llm.model
        self._temperature = settings.llm.temperature
        self._max_tokens = settings.llm.max_tokens
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0),
            )
        return self._client

    async def check_connection(self) -> bool:
        try:
            client = self._get_client()
            response = await client.get("/v1/models", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.warning("OpenAI-compat server not reachable: %s", e)
            return False

    async def complete(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            payload["tools"] = tools

        client = self._get_client()
        response = await client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

        return LLMResponse(
            content=message.get("content", "") or "",
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            model=data.get("model", self._model),
            tool_calls=[
                {"name": tc["function"]["name"], "arguments": json.loads(tc["function"]["arguments"])}
                for tc in message.get("tool_calls", [])
            ],
        )

    async def stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> AsyncGenerator[dict, None]:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        client = self._get_client()
        try:
            async with client.stream("POST", "/v1/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield {"type": "content", "content": content}
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except Exception as e:
            logger.error("OpenAI-compat stream error: %s", e)
            yield {"type": "error", "content": str(e)}

    @property
    def model_name(self) -> str:
        return self._model

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def create_llm_provider(settings: Optional[Settings] = None) -> LLMProvider:
    """
    Factory function - creates the appropriate LLM provider based on config.
    """
    cfg = settings or get_settings()
    provider_name = cfg.llm.provider.lower()

    logger.info("Creating LLM provider: %s (model: %s)", provider_name, cfg.llm.model)

    if provider_name in ("gpt_oss", "ollama", "gpt-oss"):
        return OllamaProvider(cfg)
    elif provider_name in ("lmstudio", "lm_studio", "openai_compat", "openai-compat"):
        return OpenAICompatibleProvider(cfg)
    else:
        logger.warning("Unknown provider '%s', falling back to Ollama", provider_name)
        return OllamaProvider(cfg)
