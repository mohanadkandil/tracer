"""Scan endpoints — single file, directory, comparison matrix, live SSE."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..config import DEMO_FILES_ROOT
from ..connectors import FileSystemConnector, GraphConnector
from ..connectors.base import BaseConnector, ConnectorEvent
from ..db import get_conn
from ..pipeline.dedup import content_hash, lookup_cached, remember
from ..pipeline.extract import extract_text
from ..pipeline.mosaic import link_findings_for_doc
from ..pipeline.queue import ScanQueue, WorkItem
from ..pipeline.routing import get_router
from ..schemas import (
    CompareRequest,
    CompareResponse,
    ScanRequest,
    ScanResponse,
    Span,
)

router = APIRouter(prefix="/scan")


def _severity(label: str, score: float) -> str:
    if label in {"EMPLOYEE_ID", "TAX_ID", "IBAN", "ADDRESS", "EMAIL", "ID_NUMBER"}:
        return "high"
    if label in {"PERSON", "SIGNATURE", "PHONE"}:
        return "medium" if score >= 0.7 else "low"
    return "low"


def _connector_for(source: str) -> BaseConnector:
    root = DEMO_FILES_ROOT
    if source == "sharepoint":
        return GraphConnector(root)
    return FileSystemConnector(root)


@router.post("/file", response_model=ScanResponse)
async def scan_file(req: ScanRequest) -> ScanResponse:
    """Scan a single file or raw text. Returns spans + tier provenance + timings."""
    file_id = str(uuid.uuid4())[:8]
    chash: str | None = None
    timing: dict[str, float] = {}
    deduped = False

    if req.text is not None:
        text = req.text
        source_path = None
    else:
        path = Path(req.path)  # type: ignore[arg-type]
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"file not found: {path}")
        t0 = time.perf_counter()
        data = await asyncio.to_thread(path.read_bytes)
        chash = content_hash(data)
        timing["read+hash_ms"] = (time.perf_counter() - t0) * 1000

        cached = lookup_cached(chash)
        if cached is not None:
            spans = [Span(**c) for c in cached]
            return ScanResponse(
                file_id=file_id,
                source_path=str(path),
                content_hash=chash,
                chars=0,
                spans=spans,
                deduped=True,
                timing_ms={"dedup_hit_ms": (time.perf_counter() - t0) * 1000},
                tiers_used=["cache"],
            )

        t0 = time.perf_counter()
        text = await asyncio.to_thread(extract_text, data, str(path))
        timing["extract_ms"] = (time.perf_counter() - t0) * 1000
        source_path = str(path)

    router_ = get_router()
    result = await asyncio.to_thread(router_.detect, text)
    timing.update(result.timing_ms)

    spans = [
        Span(
            start=s.start,
            end=s.end,
            label=s.label,
            value=s.value,
            score=s.score,
            detector=s.detector,
        )
        for s in result.spans
    ]

    # Persist findings (skip if scanning raw text)
    if source_path is not None:
        _persist_findings(file_id, source_path, spans)
        # Build mosaic links so DSAR + person lookups see this doc
        link_findings_for_doc(file_id, source_path, owner=None, text=text, spans=spans)
        if chash:
            remember(chash, [s.model_dump() for s in spans])

    return ScanResponse(
        file_id=file_id,
        source_path=source_path,
        content_hash=chash,
        chars=len(text),
        spans=spans,
        deduped=deduped,
        timing_ms=timing,
        tiers_used=result.tiers_used,
    )


@router.post("/all", response_model=CompareResponse)
async def scan_all(req: CompareRequest) -> CompareResponse:
    """Run each detector independently. Powers the comparison matrix UI."""
    router_ = get_router()
    detectors: dict[str, object] = {
        "presidio": router_.presidio,
        "gliner": router_.gliner,
    }
    reasoner = router_.reasoner

    requested = req.models or list(detectors.keys()) + ["reasoner"]
    out_spans: dict[str, list[Span]] = {}
    timings: dict[str, float] = {}

    for name in requested:
        t0 = time.perf_counter()
        if name == "reasoner":
            # Reasoner doesn't produce spans on its own; show it as "would verify"
            out_spans[name] = []
        elif name in detectors:
            spans = await asyncio.to_thread(detectors[name].detect, req.text)
            out_spans[name] = [
                Span(
                    start=s.start,
                    end=s.end,
                    label=s.label,
                    value=s.value,
                    score=s.score,
                    detector=s.detector,
                )
                for s in spans
            ]
        else:
            out_spans[name] = []
        timings[name] = (time.perf_counter() - t0) * 1000

    return CompareResponse(text=req.text, results=out_spans, timing_ms=timings)


@router.get("/stream")
async def scan_stream(source: str = "filesystem"):
    """Walk the demo folder, scan every file, stream progress via SSE.

    Real production version: this drives the Discovery → Queue → Worker pipeline
    against Microsoft Graph. Demo: same path, mock connector emits real local files.
    """
    connector = _connector_for(source)
    router_ = get_router()

    async def event_gen():
        yield _sse("start", {"source": source})
        scanned = 0
        deduped = 0
        findings = 0
        started = time.perf_counter()
        async for ev in connector.discover():
            try:
                data = await connector.read_bytes(ev)
            except Exception:
                continue
            chash = content_hash(data)
            cached = lookup_cached(chash)
            if cached is not None:
                deduped += 1
                scanned += 1
                yield _sse(
                    "progress",
                    {
                        "scanned": scanned,
                        "deduped": deduped,
                        "findings": findings,
                        "current": ev.path,
                        "cached": True,
                    },
                )
                continue
            text = await asyncio.to_thread(extract_text, data, ev.path)
            result = await asyncio.to_thread(router_.detect, text)
            scanned += 1
            findings += len(result.spans)
            spans_dump = [
                {
                    "start": s.start,
                    "end": s.end,
                    "label": s.label,
                    "value": s.value,
                    "score": s.score,
                    "detector": s.detector,
                }
                for s in result.spans
            ]
            remember(chash, spans_dump)
            file_id = str(uuid.uuid4())[:8]
            spans_models = [Span(**s) for s in spans_dump]
            _persist_findings(file_id, ev.path, spans_models, owner=ev.owner)
            link_findings_for_doc(file_id, ev.path, ev.owner, text, spans_models)
            yield _sse(
                "progress",
                {
                    "scanned": scanned,
                    "deduped": deduped,
                    "findings": findings,
                    "current": ev.path,
                    "owner": ev.owner,
                    "spans": len(result.spans),
                    "elapsed_ms": (time.perf_counter() - started) * 1000,
                },
            )
        yield _sse(
            "done",
            {
                "scanned": scanned,
                "deduped": deduped,
                "findings": findings,
                "elapsed_ms": (time.perf_counter() - started) * 1000,
            },
        )

    return StreamingResponse(event_gen(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _persist_findings(file_id: str, file_path: str, spans: list[Span], owner: str | None = None) -> None:
    if not spans:
        return
    with get_conn() as conn:
        for s in spans:
            conn.execute(
                "INSERT INTO findings (file_id, file_path, label, value, score, severity, owner, detector, span_start, span_end) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    file_id,
                    file_path,
                    s.label,
                    s.value,
                    s.score,
                    _severity(s.label, s.score),
                    owner,
                    s.detector,
                    s.start,
                    s.end,
                ),
            )
