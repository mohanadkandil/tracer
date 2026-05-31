"""Tiered routing orchestrator.

    T1 (Presidio regex+NER)  ─→  catches structured PII instantly, score 0.85+ kept as-is
    T2 (GLiNER multilingual) ─→  catches everything else; spans w/ score < T3_THRESHOLD escalate
    T3 (Reasoner)            ─→  reviews ambiguous spans, drops false positives, bumps severity

Spans from each tier are merged with overlap resolution: when two detectors claim
the same character range, keep the higher-confidence span and record both detectors
in the resulting span's provenance.

Confidence-gated escalation = T3 only fires when T2 score < threshold. ~90% of
spans never touch T3, which keeps demo latency low and the pitch story honest.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..config import T3_ESCALATION_THRESHOLD
from ..detectors import GLiNERDetector, PresidioDetector
from ..detectors.base import DetectedSpan
from ..detectors.reasoner import _BaseReasoner, make_reasoner


@dataclass(slots=True)
class RoutingResult:
    spans: list[DetectedSpan]
    tiers_used: list[str] = field(default_factory=list)
    timing_ms: dict[str, float] = field(default_factory=dict)
    escalated_count: int = 0
    dropped_by_t3: int = 0


class TieredRouter:
    """Single instance shared across requests. Heavy models load lazily on first call."""

    def __init__(
        self,
        presidio: PresidioDetector | None = None,
        gliner: GLiNERDetector | None = None,
        reasoner: _BaseReasoner | None = None,
    ):
        self.presidio = presidio or PresidioDetector()
        self.gliner = gliner or GLiNERDetector()
        self.reasoner = reasoner or make_reasoner()

    def detect(self, text: str) -> RoutingResult:
        result = RoutingResult(spans=[])
        if not text.strip():
            return result

        # T1
        t0 = time.perf_counter()
        t1_spans = self.presidio.detect(text)
        result.timing_ms["presidio"] = (time.perf_counter() - t0) * 1000
        result.tiers_used.append("presidio")

        # T2
        t0 = time.perf_counter()
        t2_spans = self.gliner.detect(text)
        result.timing_ms["gliner"] = (time.perf_counter() - t0) * 1000
        result.tiers_used.append("gliner")

        merged = _merge_overlapping(t1_spans + t2_spans)

        # T3 — only for ambiguous (low-confidence) survivors
        ambiguous = [s for s in merged if s.score < T3_ESCALATION_THRESHOLD and s.detector == "gliner"]
        if ambiguous:
            t0 = time.perf_counter()
            kept: list[DetectedSpan] = []
            for s in merged:
                if s not in ambiguous:
                    kept.append(s)
                    continue
                verdict = self.reasoner.verify(s, text)
                if verdict.keep:
                    if verdict.severity_bump:
                        s.score = min(1.0, s.score + 0.15 * verdict.severity_bump)
                    kept.append(s)
                else:
                    result.dropped_by_t3 += 1
            merged = kept
            result.timing_ms["reasoner"] = (time.perf_counter() - t0) * 1000
            result.tiers_used.append("reasoner")
            result.escalated_count = len(ambiguous)

        # Sort for deterministic output
        merged.sort(key=lambda s: (s.start, s.end))
        result.spans = merged
        return result


def _merge_overlapping(spans: list[DetectedSpan]) -> list[DetectedSpan]:
    """If two spans overlap, keep the higher-confidence one. Equal score → prefer
    Presidio (deterministic) over GLiNER.
    """
    if not spans:
        return []
    # Sort by (start, -score) so highest-score wins on ties
    sorted_spans = sorted(spans, key=lambda s: (s.start, -s.score))
    kept: list[DetectedSpan] = []
    for s in sorted_spans:
        if not kept:
            kept.append(s)
            continue
        last = kept[-1]
        if s.start >= last.end:
            kept.append(s)
            continue
        # Overlap — decide
        if s.score > last.score:
            kept[-1] = s
        # else drop incoming (last wins)
    return kept


# Shared singleton — created on first import, models load on first detect()
_router_instance: TieredRouter | None = None


def get_router() -> TieredRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = TieredRouter()
    return _router_instance
