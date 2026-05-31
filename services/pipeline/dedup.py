"""Content-hash dedup. If we've already scanned bytes with this SHA256, replay
the cached spans instead of re-running the model. Cheap, deterministic, eliminates
60-90% of work on monthly re-scans (where most files are unchanged).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..db import get_conn


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lookup_cached(hash_hex: str) -> list[dict[str, Any]] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT spans_json FROM scan_seen WHERE content_hash = ?",
            (hash_hex,),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["spans_json"])


def remember(hash_hex: str, spans: list[dict[str, Any]]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO scan_seen (content_hash, spans_json) VALUES (?, ?)",
            (hash_hex, json.dumps(spans)),
        )
