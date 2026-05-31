"""Mosaic API — entity identity lookup + force-directed graph + risk score + suggestions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..pipeline.mosaic import build_graph, canonical_person, lookup_person, _is_false_person

router = APIRouter(prefix="/mosaic")


@router.get("/person")
def get_person(q: str, fuzzy: bool = True) -> dict:
    """Resolve a person across all scanned docs. Returns identifiers + files +
    fuzzy aliases + re-id risk score.
    """
    result = lookup_person(q, fuzzy=fuzzy)
    if not result:
        raise HTTPException(status_code=404, detail=f"no records for {q!r}")
    return {
        "query": q,
        "canonical": result.canonical,
        "display_name": result.display_name,
        "files": result.files,
        "file_count": len(result.files),
        "identifiers": result.identifiers,
        "fuzzy_matches": [
            {"canonical": c, "value": v, "similarity": round(s, 3)}
            for c, v, s in result.fuzzy_matches
        ],
        "re_id_risk": result.re_id_risk,
        "risk_factors": result.risk_factors,
    }


@router.get("/graph")
def get_graph(limit_people: int = 50) -> dict:
    """Force-directed graph payload for the mosaic visualization."""
    return build_graph(limit_people=limit_people)


@router.get("/canonical")
def canonical(name: str) -> dict:
    """Show how a name canonicalizes."""
    return {"input": name, "canonical": canonical_person(name)}


@router.get("/suggestions")
def suggestions(limit: int = 8) -> list[dict]:
    """Return real PERSON names found in scans — useful for demo / search auto-fill.

    Filters out false positives (German form labels, single-word labels) so the
    list is high-quality.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT value, COUNT(DISTINCT file_id) AS docs "
            "FROM entity_links WHERE label = 'PERSON' "
            "GROUP BY value ORDER BY docs DESC LIMIT ?",
            (limit * 4,),  # over-fetch since we filter
        ).fetchall()
    out: list[dict] = []
    for r in rows:
        if _is_false_person(r["value"]):
            continue
        # Sanity: must look like a multi-word name (FirstName LastName style)
        parts = r["value"].split()
        if len(parts) < 2:
            continue
        out.append({"name": r["value"], "docs": r["docs"]})
        if len(out) >= limit:
            break
    return out
