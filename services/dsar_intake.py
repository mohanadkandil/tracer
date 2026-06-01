"""DSAR intake — parse a free-form erasure request into identifiers, persist
as a pending request, fire notification.

Sources supported:
  - paste-in web form (source="web")
  - REST API webhook (source="api" or "webhook")
  - Slack slash command (source="slack")
  - Email inbox (source="email" — body is full RFC 5322 message)

The parser is intentionally simple and conservative: extract candidate name
phrases, email addresses, employee IDs, phone-like sequences. The downstream
DSAR planner uses these to find files.
"""

from __future__ import annotations

import email as email_lib
from email import policy as email_policy
import json
import re
import uuid
from typing import Any

from .db import get_conn
from .notifications import dispatch
from .schemas import DSARIntakeRequest

EMP_ID_RE = re.compile(r"\bE-\d{4,6}\b")
EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+")
# "I, Hans Müller, ..." style declarations
SUBJECT_DECLARATION_RE = re.compile(
    r"(?:I,\s+|I am\s+|My name is\s+|This is\s+|Ich,\s+|Mein Name ist\s+|Hiermit\s+)"
    r"([A-ZÄÖÜ][\wäöüß\-]+(?:\s+[A-ZÄÖÜ][\wäöüß\-]+){1,3})",
)
# Loose name match — used as fallback only
NAME_FALLBACK_RE = re.compile(r"\b([A-ZÄÖÜ][a-zäöüß]{2,}\s+[A-ZÄÖÜ][a-zäöüß]{2,})\b")
ARTICLE_RE = re.compile(r"\bArt(?:icle|\.)?\s*(\d{1,2})\b", re.IGNORECASE)


def parse_intake(body: str | None,
                 subject: str | None = None,
                 requester_email: str | None = None) -> dict[str, Any]:
    """Extract subject + identifiers from a free-form erasure request."""
    body = (body or "").strip()

    # 1. If body is an RFC 5322 email, peel it
    parsed_body, parsed_from, parsed_subject = _try_parse_email(body)
    body = parsed_body or body
    requester_email = requester_email or parsed_from

    # 2. Extract identifiers
    emails = list(dict.fromkeys(EMAIL_RE.findall(body)))
    if requester_email:
        emails = [requester_email] + [e for e in emails if e != requester_email]
    emp_ids = list(dict.fromkeys(EMP_ID_RE.findall(body)))

    # 3. Extract subject name
    if not subject:
        m = SUBJECT_DECLARATION_RE.search(body)
        if m:
            subject = m.group(1).strip()
        elif parsed_subject:
            subject = parsed_subject.strip()
        else:
            # Last resort — first plausible 2-word name in body
            f = NAME_FALLBACK_RE.search(body)
            subject = f.group(1).strip() if f else ""

    # 4. Article
    article = "17"
    m = ARTICLE_RE.search(body)
    if m:
        candidate = m.group(1)
        if candidate in {"5", "17", "32"}:
            article = candidate

    # 5. Identifier list — name + emails + emp ids, deduped
    identifiers = [subject] if subject else []
    identifiers += [e for e in emails if e not in identifiers]
    identifiers += [e for e in emp_ids if e not in identifiers]

    return {
        "subject": subject or "Unknown subject",
        "requester_email": requester_email,
        "article": article,
        "identifiers": identifiers,
    }


_HEADER_RE = re.compile(r"^([A-Z][A-Za-z0-9\-]+):\s*(.+)$")


def _try_parse_email(body: str) -> tuple[str | None, str | None, str | None]:
    """Best-effort RFC 5322 split. Returns (clean_body, from, subject) or Nones.

    We DON'T use the email std lib because it round-trips UTF-8 poorly when no
    Content-Type charset header is present (mangles ü, ö, ß etc). Manual split
    preserves the original encoding intact.
    """
    if "\n" not in body:
        return None, None, None
    # Headers end at the first blank line
    split = re.split(r"\n\s*\n", body, maxsplit=1)
    if len(split) != 2:
        return None, None, None
    header_block, clean_body = split
    headers: dict[str, str] = {}
    for line in header_block.splitlines():
        m = _HEADER_RE.match(line.strip())
        if m:
            headers[m.group(1).lower()] = m.group(2).strip()
    # Heuristic: must look like an email header block
    if not any(k in headers for k in ("from", "subject", "to", "date")):
        return None, None, None
    from_email = None
    if "from" in headers:
        m = EMAIL_RE.search(headers["from"])
        if m:
            from_email = m.group(0)
    return clean_body.strip(), from_email, headers.get("subject")


def create_request(req: DSARIntakeRequest) -> dict[str, Any]:
    """Persist a new pending DSAR + fire notification."""
    parsed = parse_intake(req.body, subject=req.subject, requester_email=req.requester_email)
    parsed["article"] = req.article  # explicit override wins

    request_id = f"dsar-{uuid.uuid4().hex[:8]}"

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO dsar_requests "
            "(id, subject, requester_email, article, source, raw_email, identifiers_json, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
            (
                request_id,
                parsed["subject"],
                parsed["requester_email"],
                parsed["article"],
                req.source,
                (req.body or "")[:8000],
                json.dumps(parsed["identifiers"]),
            ),
        )

    return {
        "id": request_id,
        "subject": parsed["subject"],
        "requester_email": parsed["requester_email"],
        "article": parsed["article"],
        "source": req.source,
        "identifiers": parsed["identifiers"],
        "status": "pending",
    }


async def fire_new_request_notification(req: dict[str, Any], frontend_origin: str) -> None:
    """Send dsar_new notification to in-app SSE + optional Slack."""
    title = f"New erasure request — {req['subject']}"
    body_lines = [
        f"*Subject:* {req['subject']}",
        f"*Article:* {req['article']}",
        f"*Source:* {req['source']}",
    ]
    if req.get("requester_email"):
        body_lines.append(f"*Requester:* {req['requester_email']}")
    if req.get("identifiers"):
        ids_preview = ", ".join(req["identifiers"][:5])
        body_lines.append(f"*Identifiers:* {ids_preview}")

    await dispatch(
        kind="dsar_new",
        title=title,
        body="\n".join(body_lines),
        target_url=f"{frontend_origin}/dsar/{req['id']}",
        request_id=req["id"],
    )


def get_request(request_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM dsar_requests WHERE id = ?", (request_id,)).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_requests(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    sql = "SELECT * FROM dsar_requests"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def decide(request_id: str, decision: str, note: str | None, by: str | None) -> dict[str, Any] | None:
    if decision not in {"approve", "decline"}:
        raise ValueError("decision must be approve|decline")
    new_status = "approved" if decision == "approve" else "declined"
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE dsar_requests SET status = ?, decided_at = CURRENT_TIMESTAMP, "
            "decided_by = ?, decision_note = ? WHERE id = ? AND status = 'pending'",
            (new_status, by, note, request_id),
        )
        if cur.rowcount == 0:
            return None
    return get_request(request_id)


def mark_executed(request_id: str, files: int, erased: int, cert_path: str | None) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE dsar_requests SET status = 'executed', files_processed = ?, "
            "findings_erased = ?, cert_pdf_path = ? WHERE id = ?",
            (files, erased, cert_path, request_id),
        )
        if cur.rowcount == 0:
            return None
    return get_request(request_id)


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "subject": row["subject"],
        "requester_email": row["requester_email"],
        "article": row["article"],
        "source": row["source"],
        "identifiers": json.loads(row["identifiers_json"]) if row["identifiers_json"] else [],
        "status": row["status"],
        "created_at": row["created_at"],
        "decided_at": row["decided_at"],
        "decided_by": row["decided_by"],
        "decision_note": row["decision_note"],
        "files_processed": row["files_processed"] or 0,
        "findings_erased": row["findings_erased"] or 0,
        "cert_pdf_path": row["cert_pdf_path"],
    }
