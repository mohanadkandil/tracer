"""Notification fan-out.

Every notification is persisted in SQLite (durable) and pushed to an in-process
async pub/sub so the SSE endpoint can stream it live to any connected dashboard.
If SLACK_WEBHOOK_URL is set, also POST to Slack — same payload, real channel.

Same pattern as production webhook delivery: persist first, then attempt
delivery. If Slack POST fails, the record stays in the DB and the in-app
notification still fires.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from typing import Any

import httpx

from .db import get_conn

log = logging.getLogger("notifications")

# In-process subscribers — set of asyncio.Queues fed by `dispatch`
_subscribers: set[asyncio.Queue] = set()
# Last 50 notifications for any client that connects mid-stream
_replay_buffer: deque[dict[str, Any]] = deque(maxlen=50)


async def dispatch(kind: str, title: str, body: str | None = None,
                   target_url: str | None = None, request_id: str | None = None) -> dict[str, Any]:
    """Persist + fan out + Slack-relay (if configured)."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO notifications (kind, title, body, target_url, request_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (kind, title, body, target_url, request_id),
        )
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM notifications WHERE id = ?", (new_id,)).fetchone()

    payload = {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "target_url": row["target_url"],
        "request_id": row["request_id"],
        "created_at": row["created_at"],
        "seen": False,
    }

    _replay_buffer.append(payload)
    for q in list(_subscribers):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            log.warning("subscriber queue full; dropping notification")

    # Optional Slack relay — non-blocking, never raises into request path
    slack_url = os.environ.get("SLACK_WEBHOOK_URL")
    if slack_url:
        asyncio.create_task(_relay_slack(slack_url, payload))

    return payload


async def _relay_slack(webhook_url: str, n: dict[str, Any]) -> None:
    """Post a Block Kit payload to Slack incoming webhook."""
    block_kit = _build_block_kit(n)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(webhook_url, json=block_kit)
            if r.status_code >= 400:
                log.warning("slack relay failed %d: %s", r.status_code, r.text[:200])
    except Exception:
        log.exception("slack relay raised")


def _build_block_kit(n: dict[str, Any]) -> dict[str, Any]:
    """Slack Block Kit message. Renders identical wherever it lands."""
    icon = "🛡" if n["kind"] == "dsar_new" else "✓" if n["kind"] == "dsar_executed" else "ℹ"
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{icon}  {n['title']}"}},
    ]
    if n.get("body"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": n["body"]}})
    if n.get("target_url"):
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "Review request →"},
                "url": n["target_url"],
                "style": "primary",
            }],
        })
    return {"text": n["title"], "blocks": blocks}


# Subscriber registration ----------------------------------------------------


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=128)
    _subscribers.add(q)
    # Prime with the recent replay buffer so a freshly-connected client
    # immediately sees the recent history without needing a separate fetch.
    for item in list(_replay_buffer):
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            break
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


def list_recent(limit: int = 50, unseen_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM notifications"
    params: list[Any] = []
    if unseen_only:
        sql += " WHERE seen = 0"
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": r["id"], "kind": r["kind"], "title": r["title"], "body": r["body"],
            "target_url": r["target_url"], "request_id": r["request_id"],
            "created_at": r["created_at"], "seen": bool(r["seen"]),
        }
        for r in rows
    ]


def mark_seen(notif_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE notifications SET seen = 1 WHERE id = ?", (notif_id,))
