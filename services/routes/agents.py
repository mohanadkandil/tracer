"""Agents registry — list + endorse. Seeded on first GET.

Borrowed from the Agent SharePoint hackathon brief: every internal AI agent in
the platform is itself an artifact with structured metadata, versioning, and
endorsements. Makes the platform look like an ecosystem, not a script.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..schemas import Agent

router = APIRouter(prefix="/agents")

SEED: list[Agent] = [
    Agent(
        id="discovery",
        name="Discovery Agent",
        version="0.3.1",
        domain="ingestion",
        description="Crawls SharePoint, OneDrive, and shared drives via delta sync. Dispatches scan jobs.",
        tools=["msgraph", "asyncio.Queue"],
        inputs=["site_id", "delta_token"],
        outputs=["ConnectorEvent[]"],
    ),
    Agent(
        id="triage",
        name="Triage Classifier",
        version="0.5.0",
        domain="detection",
        description="First-pass PII labeller. GLiNER fine-tuned on Bosch-style docs. CPU, <100ms/doc.",
        tools=["gliner-bosch-ft", "presidio"],
        inputs=["text"],
        outputs=["DetectedSpan[]"],
    ),
    Agent(
        id="reasoner",
        name="Deep Reasoner",
        version="0.2.0",
        domain="detection",
        description="Resolves ambiguous spans + drafts plain-language explanations. Local LFM2.5.",
        tools=["lfm2-1.2b"],
        inputs=["span", "context"],
        outputs=["Verdict"],
    ),
    Agent(
        id="owner-resolver",
        name="Owner Resolver",
        version="0.1.0",
        domain="attribution",
        description="Maps file → person (OneDrive owner / SharePoint Master of Data).",
        tools=["msgraph", "aad"],
        inputs=["file_id"],
        outputs=["owner_email"],
    ),
    Agent(
        id="dsar",
        name="DSAR Copilot",
        version="0.4.0",
        domain="compliance",
        description="Article 17 erasure workflow + signed compliance certificate generator.",
        tools=["pgvector", "lfm2-1.2b"],
        inputs=["subject", "article"],
        outputs=["DSARPlan", "certificate.pdf"],
    ),
    Agent(
        id="mosaic",
        name="Mosaic Linker",
        version="0.1.0",
        domain="re-identification-risk",
        description="Cross-document re-id risk graph. Detects when weak PII fragments link to the same person.",
        tools=["pgvector", "voyage-3-lite"],
        inputs=["finding[]"],
        outputs=["mosaic_graph"],
    ),
]


def _ensure_seeded() -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM agents").fetchone()
        if row["c"] > 0:
            return
        for a in SEED:
            conn.execute(
                "INSERT INTO agents (id, name, version, domain, description, tools_json, inputs_json, outputs_json, endorsements) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    a.id,
                    a.name,
                    a.version,
                    a.domain,
                    a.description,
                    json.dumps(a.tools),
                    json.dumps(a.inputs),
                    json.dumps(a.outputs),
                    a.endorsements,
                ),
            )


@router.get("", response_model=list[Agent])
def list_agents() -> list[Agent]:
    _ensure_seeded()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY endorsements DESC, name ASC").fetchall()
    return [_row_to_agent(r) for r in rows]


@router.get("/{aid}", response_model=Agent)
def get_agent(aid: str) -> Agent:
    _ensure_seeded()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (aid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="agent not found")
    return _row_to_agent(row)


@router.post("/{aid}/endorse", response_model=Agent)
def endorse(aid: str) -> Agent:
    _ensure_seeded()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (aid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="agent not found")
        conn.execute("UPDATE agents SET endorsements = endorsements + 1 WHERE id = ?", (aid,))
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (aid,)).fetchone()
    return _row_to_agent(row)


def _row_to_agent(row) -> Agent:
    return Agent(
        id=row["id"],
        name=row["name"],
        version=row["version"],
        domain=row["domain"],
        description=row["description"],
        tools=json.loads(row["tools_json"]),
        inputs=json.loads(row["inputs_json"]),
        outputs=json.loads(row["outputs_json"]),
        endorsements=row["endorsements"],
    )
