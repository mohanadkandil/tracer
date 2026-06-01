"""DSAR lifecycle endpoints.

Flow:
  1. POST /dsar/inbox             (any source) → creates pending request, fires notification
  2. GET  /dsar/requests          list w/ optional status filter
  3. GET  /dsar/requests/{id}     details + computed plan + mosaic identity
  4. POST /dsar/requests/{id}/decide   approve | decline
  5. POST /dsar/requests/{id}/execute  (only after approve) → erase findings, gen cert, email
  6. POST /dsar/plan              legacy preview-only endpoint (no persist)
  7. POST /dsar/execute           legacy direct-execute (no request lifecycle)

Notifications:
  - SSE stream at /dsar/notifications/stream
  - REST list at /dsar/notifications

Slack: if SLACK_WEBHOOK_URL is set, every notification is also POSTed there.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse

from ..cert import generate_cert, send_email_stub
from ..db import get_conn
from ..detectors.reasoner import make_reasoner
from ..dsar_intake import (
    create_request,
    decide as decide_request,
    fire_new_request_notification,
    get_request,
    list_requests,
    mark_executed,
)
from ..notifications import (
    dispatch,
    list_recent as list_notifications,
    mark_seen,
    subscribe,
    unsubscribe,
)
from ..pipeline.mosaic import lookup_person
from ..schemas import (
    DSARDecision,
    DSARIntakeRequest,
    DSARMatch,
    DSARPlan,
    DSARRequest,
)

router = APIRouter(prefix="/dsar")

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")


# ---------- intake ----------


@router.post("/inbox")
async def inbox(req: DSARIntakeRequest) -> dict:
    """Universal intake — pass email body / chat text / form payload here.

    Returns the created request immediately. Notification fan-out happens
    in the background.
    """
    if not req.body and not req.subject:
        raise HTTPException(status_code=400, detail="provide `body` or `subject`")
    created = create_request(req)
    asyncio.create_task(fire_new_request_notification(created, FRONTEND_ORIGIN))
    return created


@router.get("/requests")
def list_dsar(status: str | None = None) -> list[dict]:
    return list_requests(status=status, limit=100)


@router.get("/requests/{request_id}")
def get_dsar(request_id: str) -> dict:
    req = get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="request not found")
    # Attach the computed forgetting plan + mosaic identity for the review UI
    plan = _build_plan(req["subject"], req["article"])
    identity = _mosaic_for(req["subject"])
    return {**req, "plan": plan.model_dump(), "identity": identity}


@router.post("/requests/{request_id}/decide")
async def post_decide(request_id: str, body: DSARDecision) -> dict:
    updated = decide_request(request_id, body.decision, body.note, body.decided_by)
    if not updated:
        raise HTTPException(status_code=409, detail="request not pending or not found")
    await dispatch(
        kind="system",
        title=f"DSAR {body.decision}d — {updated['subject']}",
        body=f"by *{body.decided_by or 'anonymous'}* · {body.note or 'no note'}",
        target_url=f"{FRONTEND_ORIGIN}/dsar/{request_id}",
        request_id=request_id,
    )
    return updated


@router.post("/requests/{request_id}/execute")
async def post_execute(request_id: str) -> dict:
    req = get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="request not found")
    if req["status"] not in {"approved", "pending"}:
        raise HTTPException(status_code=409, detail=f"cannot execute from status={req['status']}")

    # Compute plan again (live data may have shifted since approval)
    plan = _build_plan(req["subject"], req["article"])
    to_delete = [m for m in plan.matches if m.proposed_action == "delete"]

    erased = 0
    if to_delete:
        with get_conn() as conn:
            for m in to_delete:
                cur = conn.execute("DELETE FROM findings WHERE file_path = ?", (m.file_path,))
                erased += cur.rowcount
                conn.execute("DELETE FROM entity_links WHERE file_path = ?", (m.file_path,))

    cert_path = generate_cert(
        request_id=request_id,
        subject=req["subject"],
        article=req["article"],
        files_processed=len(to_delete),
        findings_erased=erased,
        matches=[m.model_dump() for m in to_delete],
    )
    updated = mark_executed(request_id, files=len(to_delete), erased=erased, cert_path=str(cert_path))

    # Optional outbound email reply with the cert attached
    if req.get("requester_email"):
        send_email_stub(
            to=req["requester_email"],
            subject_line=f"GDPR Art. {req['article']} erasure confirmation — {request_id}",
            body=(
                f"Dear {req['subject']},\n\n"
                f"Your erasure request under Article {req['article']} GDPR has been processed.\n"
                f"Files processed: {len(to_delete)}\n"
                f"Findings erased: {erased}\n\n"
                f"Please find the signed certificate of erasure attached.\n\n"
                f"Bosch DPO Office"
            ),
            attachment_path=cert_path,
        )

    await dispatch(
        kind="dsar_executed",
        title=f"DSAR executed — {req['subject']}",
        body=(f"*{len(to_delete)} files* · *{erased} findings* erased. "
              f"Certificate ready."),
        target_url=f"{FRONTEND_ORIGIN}/dsar/{request_id}",
        request_id=request_id,
    )
    return updated or {}


# ---------- certificate download ----------


@router.get("/requests/{request_id}/certificate")
def get_cert(request_id: str) -> FileResponse:
    req = get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="request not found")
    path = req.get("cert_pdf_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="certificate not yet generated")
    return FileResponse(path, media_type="application/pdf",
                        filename=f"erasure-cert-{request_id}.pdf")


# ---------- notifications ----------


@router.get("/notifications")
def list_notifs(unseen_only: bool = False, limit: int = 50) -> list[dict]:
    return list_notifications(limit=limit, unseen_only=unseen_only)


@router.post("/notifications/{notif_id}/seen")
def post_seen(notif_id: int) -> dict:
    mark_seen(notif_id)
    return {"ok": True}


@router.get("/notifications/stream")
async def stream_notifs():
    """SSE stream — every notification is delivered live."""
    q = subscribe()

    async def gen():
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"event: notification\ndata: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------- legacy preview-only endpoints (still used by current UI) ----------


@router.post("/plan", response_model=DSARPlan)
def plan(req: DSARRequest) -> DSARPlan:
    return _build_plan(req.subject, req.article)


@router.post("/execute")
def execute(req: DSARRequest) -> dict:
    """Legacy direct-execute (no request lifecycle). Kept for the old UI button."""
    plan_obj = _build_plan(req.subject, req.article)
    affected = [m.file_path for m in plan_obj.matches if m.proposed_action == "delete"]
    erased = 0
    if affected:
        with get_conn() as conn:
            for p in affected:
                cur = conn.execute("DELETE FROM findings WHERE file_path = ?", (p,))
                erased += cur.rowcount
    return {
        "subject": req.subject,
        "article": req.article,
        "files_processed": len(affected),
        "findings_erased": erased,
        "certificate_url": f"/dsar/legacy-cert?subject={req.subject}",
    }


# ---------- internal helpers ----------


_EMP_ID_RE = re.compile(r"\bE-\d{4,6}\b")
_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+")


def _extract_identifiers(subject: str) -> list[str]:
    ids: set[str] = {subject.strip()}
    for token in re.split(r"[\s,]+", subject):
        token = token.strip()
        if len(token) >= 3:
            ids.add(token)
    for m in _EMP_ID_RE.finditer(subject):
        ids.add(m.group())
    for m in _EMAIL_RE.finditer(subject):
        ids.add(m.group())
    return [i for i in ids if i]


def _build_plan(subject: str, article: str) -> DSARPlan:
    identifiers = _extract_identifiers(subject)
    files_matched: dict[str, list[str]] = {}
    with get_conn() as conn:
        for ident in identifiers:
            rows = conn.execute(
                "SELECT DISTINCT file_path, value FROM findings WHERE value LIKE ?",
                (f"%{ident}%",),
            ).fetchall()
            for r in rows:
                files_matched.setdefault(r["file_path"], []).append(ident)

    identity = lookup_person(subject, fuzzy=True)
    if identity is not None:
        for path in identity.files:
            files_matched.setdefault(path, []).append(identity.display_name)
        for label, values in identity.identifiers.items():
            if label == "PERSON":
                continue
            for v in values:
                for path in identity.files:
                    files_matched.setdefault(path, []).append(f"{label}:{v}")

    matches: list[DSARMatch] = []
    for path, terms in files_matched.items():
        unique_terms = sorted(set(terms))
        confidence = min(1.0, len(unique_terms) / max(1, len(identifiers)))
        action = "delete" if confidence >= 0.5 else "anonymize"
        reason = (
            f"Matched {len(unique_terms)} identifier(s) "
            f"({', '.join(unique_terms[:3])}). "
            f"Article {article} obligates erasure within statutory window."
        )
        matches.append(DSARMatch(
            file_path=path, matched_terms=unique_terms,
            confidence=confidence, proposed_action=action, reason=reason,
        ))
    matches.sort(key=lambda m: m.confidence, reverse=True)

    reasoner = make_reasoner()
    summary = reasoner.reason(
        f"Subject: {subject}\nArticle: {article}\nFiles matched: {len(matches)}\n"
        "Draft a short compliance summary."
    )
    risk_notes: list[str] = []
    if not matches:
        risk_notes.append("No matching files. Verify subject identifiers or expand search window.")
    if any(m.confidence < 0.5 for m in matches):
        risk_notes.append("Low-confidence matches present; manual DPO review recommended.")
    if identity:
        if identity.re_id_risk in {"high", "critical"}:
            risk_notes.append(
                f"Re-identification risk: {identity.re_id_risk.upper()} — "
                + "; ".join(identity.risk_factors)
            )
        if identity.fuzzy_matches:
            aliases = ", ".join(f"{v} ({sim:.2f})" for _, v, sim in identity.fuzzy_matches[:3])
            risk_notes.append(f"Fuzzy aliases linked via embedding: {aliases}")

    return DSARPlan(subject=subject, article=article, matches=matches,
                    summary=summary, risk_notes=risk_notes)


def _mosaic_for(subject: str) -> dict | None:
    """Lightweight mosaic snapshot for the review page."""
    identity = lookup_person(subject, fuzzy=True)
    if not identity:
        return None
    return {
        "canonical": identity.canonical,
        "display_name": identity.display_name,
        "file_count": len(identity.files),
        "identifiers": identity.identifiers,
        "fuzzy_matches": [
            {"canonical": c, "value": v, "similarity": round(s, 3)}
            for c, v, s in identity.fuzzy_matches
        ],
        "re_id_risk": identity.re_id_risk,
        "risk_factors": identity.risk_factors,
    }
