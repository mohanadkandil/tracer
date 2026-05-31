"""Findings list + filter + detail. Powers User View (per-owner) and Admin Dashboard."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..schemas import Finding

router = APIRouter(prefix="/findings")


@router.get("", response_model=list[Finding])
def list_findings(owner: str | None = None, label: str | None = None, limit: int = 200) -> list[Finding]:
    sql = "SELECT * FROM findings WHERE 1=1"
    params: list = []
    if owner:
        sql += " AND owner = ?"
        params.append(owner)
    if label:
        sql += " AND label = ?"
        params.append(label)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_finding(r) for r in rows]


@router.get("/summary")
def summary() -> dict:
    """Admin Dashboard KPIs: total files, total findings, by-severity, by-label."""
    with get_conn() as conn:
        files = conn.execute("SELECT COUNT(DISTINCT file_id) AS c FROM findings").fetchone()["c"]
        total = conn.execute("SELECT COUNT(*) AS c FROM findings").fetchone()["c"]
        by_severity = {
            r["severity"]: r["c"]
            for r in conn.execute("SELECT severity, COUNT(*) AS c FROM findings GROUP BY severity").fetchall()
        }
        by_label = {
            r["label"]: r["c"]
            for r in conn.execute("SELECT label, COUNT(*) AS c FROM findings GROUP BY label").fetchall()
        }
        by_detector = {
            r["detector"]: r["c"]
            for r in conn.execute("SELECT detector, COUNT(*) AS c FROM findings GROUP BY detector").fetchall()
        }
        top_owners = [
            {"owner": r["owner"], "count": r["c"]}
            for r in conn.execute(
                "SELECT owner, COUNT(*) AS c FROM findings WHERE owner IS NOT NULL "
                "GROUP BY owner ORDER BY c DESC LIMIT 10"
            ).fetchall()
        ]
    return {
        "files_with_findings": files,
        "total_findings": total,
        "by_severity": by_severity,
        "by_label": by_label,
        "by_detector": by_detector,
        "top_exposed_owners": top_owners,
    }


@router.get("/{fid}", response_model=Finding)
def get_finding(fid: int) -> Finding:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM findings WHERE id = ?", (fid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return _row_to_finding(row)


def _row_to_finding(row) -> Finding:
    return Finding(
        id=row["id"],
        file_path=row["file_path"],
        label=row["label"],
        value=row["value"],
        score=row["score"],
        severity=row["severity"],
        owner=row["owner"],
        detector=row["detector"],
        created_at=row["created_at"],
    )
