"""Chat endpoint — RAG over scanned doc chunks + DSAR + mosaic facts.

POST /chat            non-stream JSON (for testing)
GET  /chat/stream     SSE stream — emits source citations first, then tokens
GET  /chat/health     active provider + chunk count

Prompt assembly:
  system = privacy-officer assistant persona + sovereign AI guardrails
  context = top-k retrieved chunks (file path + text)
  user = the query
"""

from __future__ import annotations

import asyncio
import json
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..db import get_conn
from ..llm import active_provider, stream_chat
from ..pipeline.chunks import chunk_count, retrieve

router = APIRouter(prefix="/chat")


SYSTEM_PROMPT = """You are Forgetter, a privacy compliance assistant for Bosch's
internal data discovery platform. You answer DPO questions using the retrieved
context chunks from scanned corporate documents.

RULES:
1. Use only the provided context to answer. If the context does not contain the
   answer, say so plainly. Never invent file names, identifiers, or counts.
2. When citing facts, reference the source file in [brackets] using its path.
3. Be concise — DPOs are busy. Lead with the answer.
4. Personal data appearing in context is already scoped under their compliance
   role; you can repeat names, employee IDs, and emails when relevant to the
   answer. Do not redact unnecessarily.
5. If asked to take destructive action (erase, delete), say to use the DSAR
   flow at /dsar — never claim you've deleted anything.
6. Local-first: all processing happens on Bosch infrastructure. No data leaves.
"""


@router.get("/health")
async def health() -> dict:
    return {
        "provider": await active_provider(),
        "chunks_indexed": chunk_count(),
    }


@router.post("")
async def chat_once(req: dict) -> dict:
    """Non-stream — used for tests / curl. UI uses /chat/stream."""
    query = (req.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    chunks = retrieve(query, top_k=6)
    messages = _build_messages(query, chunks)
    out: list[str] = []
    async for tok in stream_chat(messages):
        out.append(tok)
    return {
        "query": query,
        "answer": "".join(out),
        "sources": [
            {"file_path": c.file_path, "score": round(c.score, 3), "preview": c.text[:160]}
            for c in chunks
        ],
    }


@router.get("/stream")
async def chat_stream(q: str):
    """SSE — emits one `sources` event first, then a stream of `token` events,
    then `done`. Used by the Cmd+K chat panel for live token display.
    """
    query = unquote(q).strip()
    if not query:
        raise HTTPException(status_code=400, detail="q required")

    async def gen():
        chunks = retrieve(query, top_k=6)
        sources = [
            {"file_path": c.file_path, "score": round(c.score, 3), "preview": c.text[:200]}
            for c in chunks
        ]
        yield _sse("sources", {"sources": sources, "query": query})

        if not chunks:
            yield _sse("token", {"text": "No matching documents found in the index. "
                                         "Try a different phrasing or run a scan first."})
            yield _sse("done", {})
            return

        messages = _build_messages(query, chunks)
        try:
            async for tok in stream_chat(messages):
                yield _sse("token", {"text": tok})
                # Yield to event loop so SSE flushes promptly
                await asyncio.sleep(0)
        except Exception as e:
            yield _sse("token", {"text": f"\n\n[chat error] {e}"})
        yield _sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/suggestions")
def suggestions() -> list[str]:
    """Quick-fire query chips. Mix of demo-flavored prompts + live facts."""
    base = [
        "Who is at highest re-identification risk?",
        "Which department has the most PII exposure?",
        "Show files where Hans Müller appears with his tax ID.",
        "Summarize Article 17 erasure requests in the inbox.",
        "What's the largest cluster of supplier contact data?",
        "Which file types contain the most personal data?",
    ]
    # Optionally append concrete person from current data
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM entity_links WHERE label = 'PERSON' "
            "GROUP BY value ORDER BY COUNT(DISTINCT file_id) DESC LIMIT 1"
        ).fetchone()
    if row and row["value"]:
        base.insert(0, f"What do we know about {row['value']}?")
    return base[:8]


def _build_messages(query: str, chunks) -> list[dict]:
    context_blocks = []
    for i, c in enumerate(chunks, start=1):
        context_blocks.append(f"[{i}] {c.file_path}\n{c.text}\n")
    context = "\n---\n".join(context_blocks) if context_blocks else "(no matching docs)"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content":
            f"Context from scanned documents:\n\n{context}\n\n"
            f"Question: {query}\n\n"
            f"Answer using only the context. Cite source files in [brackets]."},
    ]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
