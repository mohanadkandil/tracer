"""LLM streaming adapter.

Two providers behind a single async-generator interface:

  - ollama (default if OLLAMA_URL set, local sovereign AI)
  - openrouter (cloud fallback, cheap small model)

Switch with CHAT_PROVIDER env. Both yield raw token strings.

Pitch line: "Default provider is local Ollama. Cloud is opt-in only."
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator

import httpx

log = logging.getLogger("llm")


CHAT_PROVIDER = os.environ.get("CHAT_PROVIDER", "auto").lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_CHAT_MODEL = os.environ.get(
    "OPENROUTER_CHAT_MODEL",
    "meta-llama/llama-3.3-70b-instruct",
)


async def _ping_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


async def stream_chat(messages: list[dict], max_tokens: int = 800) -> AsyncIterator[str]:
    """Pick the active provider, stream tokens. `messages` is OpenAI-shape."""
    provider = CHAT_PROVIDER
    if provider == "auto":
        provider = "ollama" if await _ping_ollama() else "openrouter"

    if provider == "ollama":
        async for tok in _stream_ollama(messages, max_tokens):
            yield tok
        return

    if provider == "openrouter":
        if not OPENROUTER_API_KEY:
            yield "[chat] OPENROUTER_API_KEY not set and Ollama unreachable. Set one to enable chat."
            return
        async for tok in _stream_openrouter(messages, max_tokens):
            yield tok
        return

    yield f"[chat] unknown provider {provider!r}"


async def _stream_ollama(messages: list[dict], max_tokens: int) -> AsyncIterator[str]:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "options": {"num_predict": max_tokens, "temperature": 0.3},
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0)) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
                if r.status_code != 200:
                    body = await r.aread()
                    yield f"[ollama error {r.status_code}] {body.decode('utf-8', 'replace')[:300]}"
                    return
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = obj.get("message") or {}
                    content = msg.get("content", "")
                    if content:
                        yield content
                    if obj.get("done"):
                        return
    except Exception as e:
        log.exception("ollama stream failed")
        yield f"[ollama error] {e}"


async def _stream_openrouter(messages: list[dict], max_tokens: int) -> AsyncIterator[str]:
    payload = {
        "model": OPENROUTER_CHAT_MODEL,
        "messages": messages,
        "stream": True,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Forgetter",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            async with client.stream("POST", OPENROUTER_URL, json=payload, headers=headers) as r:
                if r.status_code != 200:
                    body = await r.aread()
                    yield f"[openrouter error {r.status_code}] {body.decode('utf-8', 'replace')[:300]}"
                    return
                async for line in r.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = (obj.get("choices") or [{}])[0].get("delta") or {}
                    content = delta.get("content", "")
                    if content:
                        yield content
    except Exception as e:
        log.exception("openrouter stream failed")
        yield f"[openrouter error] {e}"


async def active_provider() -> str:
    if CHAT_PROVIDER != "auto":
        return CHAT_PROVIDER
    return "ollama" if await _ping_ollama() else ("openrouter" if OPENROUTER_API_KEY else "none")
