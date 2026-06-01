"""Doc chunker + embedder + retriever.

Splits each scanned doc into ~350-char chunks with 50-char overlap, embeds
each via the same multilingual model already used for mosaic, persists vectors
in `doc_chunks`. Retriever does brute-force cosine over the table (good up to
~100K chunks; swap for sqlite-vec / pgvector at production scale).

All embedding work uses the singleton sentence-transformers model. Loads on
first call. CPU-only.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass

from ..db import get_conn
from .mosaic import get_embedder

log = logging.getLogger("pipeline.chunks")

CHUNK_SIZE = 350
CHUNK_OVERLAP = 50


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Greedy whitespace-aware chunker. Keeps chunks roughly `size` chars."""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    pos = 0
    n = len(text)
    while pos < n:
        end = min(n, pos + size)
        # Snap to nearest whitespace within the last 60 chars to avoid mid-word splits
        if end < n:
            snap = text.rfind(" ", max(pos, end - 60), end)
            if snap > pos:
                end = snap
        chunk = text[pos:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        pos = max(end - overlap, pos + 1)
    return chunks


def _pack_vector(vec) -> bytes:
    return struct.pack(f"<{len(vec)}f", *map(float, vec))


def _unpack_vector(blob: bytes, dim: int) -> list[float]:
    return list(struct.unpack(f"<{dim}f", blob))


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def index_doc(file_id: str, file_path: str, text: str) -> int:
    """Embed + persist chunks for one scanned doc. Idempotent — clears previous
    chunks for the same file_id first. Returns chunk count.
    """
    embedder = get_embedder()
    if embedder is None:
        log.debug("embedder unavailable; skipping chunk index for %s", file_path)
        return 0

    chunks = chunk_text(text)
    if not chunks:
        return 0

    try:
        vecs = embedder.encode(chunks)
    except Exception:
        log.exception("chunk embedding failed for %s", file_path)
        return 0

    with get_conn() as conn:
        conn.execute("DELETE FROM doc_chunks WHERE file_id = ?", (file_id,))
        rows = []
        for i, (chunk, vec) in enumerate(zip(chunks, vecs)):
            rows.append((file_id, file_path, i, chunk, _pack_vector(vec), len(vec)))
        conn.executemany(
            "INSERT INTO doc_chunks (file_id, file_path, chunk_index, text, vector, dim) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(chunks)


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: int
    file_path: str
    text: str
    score: float


def retrieve(query: str, top_k: int = 6, min_score: float = 0.25) -> list[RetrievedChunk]:
    """Embed query, cosine-rank against all stored chunks, return top-k."""
    embedder = get_embedder()
    if embedder is None or not query.strip():
        return []
    try:
        q_vec = list(embedder.encode([query.strip()])[0])
    except Exception:
        log.exception("query embed failed")
        return []

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, file_path, text, vector, dim FROM doc_chunks"
        ).fetchall()

    scored: list[RetrievedChunk] = []
    for r in rows:
        v = _unpack_vector(r["vector"], r["dim"])
        sim = _cosine(q_vec, v)
        if sim < min_score:
            continue
        scored.append(RetrievedChunk(
            chunk_id=r["id"], file_path=r["file_path"], text=r["text"], score=sim,
        ))
    scored.sort(key=lambda c: -c.score)
    return scored[:top_k]


def chunk_count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM doc_chunks").fetchone()["c"]
