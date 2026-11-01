"""Small OpenAI-compatible streaming gateway client."""
from __future__ import annotations

import asyncio
import inspect
import statistics
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx


@dataclass
class Completion:
    reply: str = ""
    latency_s: float | None = None
    ttft_s: float | None = None
    reasoning_ttft_s: float | None = None
    in_tok: int | None = None
    out_tok: int | None = None
    reasoning_tok: int | None = None
    finish_reason: str | None = None
    error: str | None = None
    unsupported: bool = False


class GatewayError(Exception):
    def __init__(self, error: str, message: str = "", *, unsupported: bool = False):
        super().__init__(message or error)
        self.error, self.unsupported = error, unsupported


def _usage(obj: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get("usage") or obj.get("data", {}).get("usage")
    return getattr(obj, "usage", None)


class Gateway:
    def __init__(self, base_url: str, api_key: str | None = None,
                 *, timeout: float = 600, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else api_key
        self.timeout = timeout
        self._client = client
        self._owned = client is None

    async def close(self) -> None:
        if self._owned and self._client:
            await self._client.aclose()

    async def chat(self, model: str, messages: list[dict[str, str]], *, effort: str,
                   max_tokens: int, timeout: float | None = None) -> Completion:
        client = self._client or httpx.AsyncClient(timeout=timeout or self.timeout)
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"model": model, "messages": messages, "stream": True,
                   "stream_options": {"include_usage": True}, "max_tokens": max_tokens,
                   "reasoning_effort": effort}
        started = time.perf_counter()
        try:
            async with client.stream("POST", f"{self.base_url}/chat/completions",
                                     json=payload, headers=headers,
                                     timeout=timeout or self.timeout) as response:
                if response.status_code >= 400:
                    unsupported = response.status_code == 400
                    raise GatewayError("http_error", f"HTTP {response.status_code}",
                                       unsupported=unsupported)
                reply, first, reasoning_first, finish = [], None, None, None
                in_tok = out_tok = reasoning_tok = None
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        item = __import__("json").loads(raw)
                    except ValueError:
                        continue
                    choices = item.get("choices") or []
                    if choices:
                        choice = choices[0]
                        finish = choice.get("finish_reason") or finish
                        delta = choice.get("delta") or {}
                        content = delta.get("content") or ""
                        reasoning = delta.get("reasoning_content") or ""
                        now = time.perf_counter()
                        if content and first is None: first = now - started
                        if reasoning and reasoning_first is None: reasoning_first = now - started
                        reply.append(content)
                    usage = item.get("usage")
                    if usage:
                        in_tok = usage.get("prompt_tokens", in_tok)
                        out_tok = usage.get("completion_tokens", out_tok)
                        details = usage.get("completion_tokens_details") or {}
                        reasoning_tok = details.get("reasoning_tokens", reasoning_tok)
                ended = time.perf_counter()
                if not "".join(reply):
                    raise GatewayError("empty_reply")
                return Completion("".join(reply), ended-started, first, reasoning_first,
                                  in_tok, out_tok, reasoning_tok, finish)
        except GatewayError:
            raise
        except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
            raise GatewayError("timeout", str(exc)) from exc
        except httpx.HTTPError as exc:
            raise GatewayError("network_error", str(exc)) from exc
        finally:
            if self._owned:
                await client.aclose()

    complete = chat

    async def connect_rtt_ms(self, fallback_ms: float = 30, attempts: int = 3) -> float:
        u = urlsplit(self.base_url)
        host, port = u.hostname, u.port or (443 if u.scheme == "https" else 80)
        if not host:
            return fallback_ms
        values = []
        for _ in range(attempts):
            try:
                started = time.perf_counter()
                reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), 5)
                writer.close()
                close = getattr(writer, "wait_closed", None)
                if close:
                    await close()
                values.append((time.perf_counter()-started) * 1000)
            except Exception:
                pass
        return statistics.median(values) if values else fallback_ms


GatewayClient = Gateway


async def chat_completion(base_url: str, model: str, messages: list[dict[str, str]], *,
                          api_key: str | None = None, effort: str = "medium",
                          max_tokens: int = 16384, timeout: float = 600,
                          client: httpx.AsyncClient | None = None) -> Completion:
    """Functional convenience wrapper used by small integrations and tests."""
    gateway = Gateway(base_url, api_key, timeout=timeout, client=client)
    return await gateway.chat(model, messages, effort=effort, max_tokens=max_tokens,
                              timeout=timeout)
