"""HTTP request/response models for the scan service."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]


class Span(BaseModel):
    start: int
    end: int
    label: str
    value: str
    score: float = 1.0
    detector: str  # "presidio" | "gliner" | "reasoner"


class ScanRequest(BaseModel):
    path: str | None = None
    text: str | None = None

    def model_post_init(self, __ctx) -> None:
        if not self.path and not self.text:
            raise ValueError("Provide either path or text")


class ScanResponse(BaseModel):
    file_id: str
    source_path: str | None = None
    content_hash: str | None = None
    chars: int
    spans: list[Span]
    deduped: bool = False
    timing_ms: dict[str, float] = Field(default_factory=dict)
    tiers_used: list[str] = Field(default_factory=list)


class CompareRequest(BaseModel):
    text: str
    models: list[str] | None = None  # subset of [presidio, gliner, reasoner]


class CompareResponse(BaseModel):
    text: str
    results: dict[str, list[Span]]
    timing_ms: dict[str, float]


class Finding(BaseModel):
    id: int
    file_path: str
    label: str
    value: str
    score: float
    severity: Severity
    owner: str | None = None
    detector: str
    created_at: str


class Agent(BaseModel):
    id: str
    name: str
    version: str
    domain: str
    description: str
    tools: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    endorsements: int = 0


class DSARRequest(BaseModel):
    subject: str  # natural-language identifier ("Tobias Wagner")
    article: Literal["17", "5", "32"] = "17"
    requester_email: str | None = None


class DSARMatch(BaseModel):
    file_path: str
    matched_terms: list[str]
    confidence: float
    proposed_action: Literal["delete", "anonymize", "redact", "retain"]
    reason: str


class DSARPlan(BaseModel):
    subject: str
    article: str
    matches: list[DSARMatch]
    summary: str
    risk_notes: list[str] = Field(default_factory=list)
