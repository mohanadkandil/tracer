"""DSAR (data subject access request) — Article 17 erasure workflow.

Takes a natural-language erasure request, finds all stored findings matching the
subject identifiers, produces a "Forgetting Plan" with per-file proposed actions,
and (separately) generates a compliance certificate PDF.

The matching strategy is intentionally simple for the demo: name/email substring +
employee-ID exact match. Production version uses the mosaic graph to catch indirect
links (e.g., "John, Berlin, ext 4421" identifies Elena Fischer).
"""

from __future__ import annotations

import re

from fastapi import APIRouter

from ..db import get_conn
from ..detectors.reasoner import make_reasoner
from ..schemas import DSARMatch, DSARPlan, DSARRequest

router = APIRouter(prefix="/dsar")


def _extract_identifiers(subject: str) -> list[str]:
    """Pull out plausible identifiers: full name, email, employee id."""
    ids: set[str] = {subject.strip()}
    # First/last names from a multi-word subject
    parts = [p for p in re.split(r"[\s,]+", subject) if len(p) >= 3]
    ids.update(parts)
    # Employee ID heuristic
    for m in re.finditer(r"E-\d{4,6}", subject):
        ids.add(m.group())
    return [i for i in ids if i]


@router.post("/plan", response_model=DSARPlan)
def plan(req: DSARRequest) -> DSARPlan:
    identifiers = _extract_identifiers(req.subject)

    with get_conn() as conn:
        # Match where value LIKE any identifier
        files_matched: dict[str, list[str]] = {}
        for ident in identifiers:
            rows = conn.execute(
                "SELECT DISTINCT file_path, value FROM findings WHERE value LIKE ?",
                (f"%{ident}%",),
            ).fetchall()
            for r in rows:
                files_matched.setdefault(r["file_path"], []).append(ident)

    matches: list[DSARMatch] = []
    for path, terms in files_matched.items():
        unique_terms = sorted(set(terms))
        # Confidence ≈ ratio of identifiers found in this file
        confidence = min(1.0, len(unique_terms) / max(1, len(identifiers)))
        action = "delete" if confidence >= 0.5 else "anonymize"
        reason = (
            f"Matched {len(unique_terms)} identifier(s) ({', '.join(unique_terms[:3])}). "
            f"Article {req.article} obligates erasure within statutory window."
        )
        matches.append(
            DSARMatch(
                file_path=path,
                matched_terms=unique_terms,
                confidence=confidence,
                proposed_action=action,
                reason=reason,
            )
        )

    matches.sort(key=lambda m: m.confidence, reverse=True)

    reasoner = make_reasoner()
    summary = reasoner.reason(
        f"Subject: {req.subject}\nArticle: {req.article}\nFiles matched: {len(matches)}\n"
        "Draft a short compliance summary."
    )

    risk_notes: list[str] = []
    if not matches:
        risk_notes.append("No matching files. Verify subject identifiers or expand the search window.")
    if any(m.confidence < 0.5 for m in matches):
        risk_notes.append(
            "Low-confidence matches present; manual DPO review recommended before destructive action."
        )

    return DSARPlan(
        subject=req.subject,
        article=req.article,
        matches=matches,
        summary=summary,
        risk_notes=risk_notes,
    )


@router.post("/execute")
def execute(req: DSARRequest) -> dict:
    """Demo-mode execution: mark findings as erased in DB, do NOT touch real files."""
    p = plan(req)
    affected_files = [m.file_path for m in p.matches if m.proposed_action == "delete"]
    erased = 0
    if affected_files:
        with get_conn() as conn:
            for path in affected_files:
                cur = conn.execute("DELETE FROM findings WHERE file_path = ?", (path,))
                erased += cur.rowcount
    return {
        "subject": req.subject,
        "article": req.article,
        "files_processed": len(affected_files),
        "findings_erased": erased,
        "certificate_url": f"/dsar/certificate?subject={req.subject}",
    }
