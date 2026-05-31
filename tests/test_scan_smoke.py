"""Smoke tests for the scan service. Production-grade primitives prove they work."""

from __future__ import annotations

import glob

import pytest
from fastapi.testclient import TestClient

from services.app import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_agents_seeded() -> None:
    """Agents registry should auto-seed on first read."""
    r = client.get("/agents")
    assert r.status_code == 200
    agents = r.json()
    assert len(agents) >= 6
    ids = {a["id"] for a in agents}
    assert {"discovery", "triage", "reasoner", "dsar", "mosaic"}.issubset(ids)


def test_endorse_agent() -> None:
    r = client.post("/agents/dsar/endorse")
    assert r.status_code == 200
    assert r.json()["endorsements"] >= 1


def test_scan_real_pdf_finds_pii() -> None:
    """Scan an actual PDF from data/files/. Must detect at least one PERSON or EMAIL."""
    candidates = sorted(glob.glob("data/files/IT/it_access_en_*.pdf"))
    if not candidates:
        pytest.skip("no PDF fixtures — run data_gen.render first")
    pdf = candidates[0]
    r = client.post("/scan/file", json={"path": pdf})
    assert r.status_code == 200
    data = r.json()
    labels = {s["label"] for s in data["spans"]}
    assert labels & {"PERSON", "EMAIL", "EMPLOYEE_ID", "USERNAME"}, f"no PII detected in {pdf}"
    # chars is 0 on cache hit (returns cached spans). Either we scanned fresh OR we hit cache.
    if not data["deduped"]:
        assert data["chars"] > 0
        assert "presidio" in data["tiers_used"]
    else:
        assert data["tiers_used"] == ["cache"]


def test_scan_dedup_cache_hit() -> None:
    """Re-scanning the same bytes must hit the dedup cache."""
    candidates = sorted(glob.glob("data/files/IT/it_access_en_*.pdf"))
    if not candidates:
        pytest.skip("no PDF fixtures")
    pdf = candidates[0]
    client.post("/scan/file", json={"path": pdf})  # warm
    r = client.post("/scan/file", json={"path": pdf})
    assert r.status_code == 200
    assert r.json()["deduped"] is True
    assert r.json()["tiers_used"] == ["cache"]


def test_compare_returns_per_model_spans() -> None:
    r = client.post("/scan/all", json={
        "text": "Employee Hans Müller (E-43217), email hans.muller@bosch.example, tax DE123456789",
        "models": ["presidio"],
    })
    assert r.status_code == 200
    data = r.json()
    assert "presidio" in data["results"]
    assert "presidio" in data["timing_ms"]


def test_findings_summary_shape() -> None:
    r = client.get("/findings/summary")
    assert r.status_code == 200
    s = r.json()
    for key in ("files_with_findings", "total_findings", "by_severity", "by_label", "by_detector", "top_exposed_owners"):
        assert key in s


def test_dsar_plan_runs() -> None:
    r = client.post("/dsar/plan", json={"subject": "Hans Müller", "article": "17"})
    assert r.status_code == 200
    data = r.json()
    assert data["subject"] == "Hans Müller"
    assert data["article"] == "17"
    assert isinstance(data["matches"], list)
    assert "summary" in data
