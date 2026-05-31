"""Mosaic API — entity identity lookup + force-directed graph + risk score.

Powers the "Privacy Mosaic" demo: paste a name, see every file that mentions
them, every identifier they're linked to, fuzzy-matched aliases, and a re-id
risk score with cited reasons.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..pipeline.mosaic import build_graph, canonical_person, lookup_person

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
    """Debug helper: show how a name canonicalizes. Useful when judges ask
    "what if I write the name differently?".
    """
    return {"input": name, "canonical": canonical_person(name)}
