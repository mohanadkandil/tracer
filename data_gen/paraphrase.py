"""Paraphrase filled examples via OpenRouter while preserving entity values verbatim.

Strategy: instruct LLM to rewrite prose but keep every listed entity string unchanged.
Then re-locate spans by exact substring match. Drop the example if any entity is missing
or duplicated (ambiguous position) after paraphrase.
"""

from __future__ import annotations

import asyncio
import os
from typing import Iterable

import httpx
from tqdm.asyncio import tqdm_asyncio

from .schemas import Entity, Example

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

PARAPHRASE_SYS = (
    "You rewrite corporate documents in varied prose to increase linguistic diversity for NER training. "
    "STRICT RULES: (1) Preserve every entity string EXACTLY as given — same spelling, capitalization, punctuation, spacing. "
    "(2) Do not add or invent any new names, IDs, emails, addresses, phone numbers, tax IDs, IBANs, or dates. "
    "(3) Keep all field labels and structure recognizable but vary sentence shape. "
    "(4) Output ONLY the rewritten document, no preamble, no explanation, no markdown fences."
)


def _build_user_prompt(text: str, entities: list[Entity]) -> str:
    bullet_lines = "\n".join(f"- {e.label}: {e.value!r}" for e in entities)
    return (
        f"Original document:\n---\n{text}\n---\n\n"
        f"Preserve these entities exactly (do not alter):\n{bullet_lines}\n\n"
        "Rewrite the document now."
    )


async def _call_openrouter(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    text: str,
    entities: list[Entity],
    temperature: float = 0.7,
) -> str:
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": 1500,
        "messages": [
            {"role": "system", "content": PARAPHRASE_SYS},
            {"role": "user", "content": _build_user_prompt(text, entities)},
        ],
    }
    r = await client.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/bosch-gdpr-hackathon",
            "X-Title": "Bosch GDPR PII fine-tune data gen",
        },
        json=payload,
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _relocate_spans(text: str, entities: list[Entity]) -> list[Entity] | None:
    """Find each entity's value as substring in new text. Reject if missing or ambiguous (multi-match)."""
    out: list[Entity] = []
    for e in entities:
        first = text.find(e.value)
        if first == -1:
            return None
        second = text.find(e.value, first + 1)
        if second != -1:
            return None  # ambiguous — drop
        out.append(Entity(start=first, end=first + len(e.value), label=e.label, value=e.value))
    out.sort(key=lambda x: x.start)
    return out


async def paraphrase_one(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    ex: Example,
    sem: asyncio.Semaphore,
) -> Example | None:
    async with sem:
        try:
            new_text = await _call_openrouter(client, api_key, model, ex.text, ex.entities)
        except Exception:
            return None
    new_entities = _relocate_spans(new_text, ex.entities)
    if new_entities is None:
        return None
    return Example(
        id=f"{ex.id}-pp",
        doc_type=ex.doc_type,
        lang=ex.lang,
        is_template=False,
        is_filled=True,
        source="paraphrase",
        text=new_text,
        entities=new_entities,
    )


async def paraphrase_batch(
    examples: Iterable[Example],
    api_key: str | None = None,
    model: str | None = None,
    concurrency: int = 8,
) -> list[Example]:
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    model = model or os.environ.get("OPENROUTER_PARAPHRASE_MODEL", "meta-llama/llama-3.3-70b-instruct")

    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(http2=False) as client:
        tasks = [paraphrase_one(client, api_key, model, ex, sem) for ex in examples]
        results = await tqdm_asyncio.gather(*tasks, desc="paraphrase")
    return [r for r in results if r is not None]
