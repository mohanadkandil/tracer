"""T1 — Presidio regex + small-model NER. Fast, deterministic, instant on CPU.

Catches the easy structured stuff (emails, IBANs, tax IDs, phone numbers) before
we burn cycles in heavier tiers. Maps Presidio's entity vocabulary to ours so
downstream code only has to know our schema.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from .base import DetectedSpan, Detector

log = logging.getLogger("detectors.presidio")

# Presidio entity → our label
LABEL_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "IBAN_CODE": "IBAN",
    "LOCATION": "ADDRESS",
    "IP_ADDRESS": "ID_NUMBER",
    "CREDIT_CARD": "ID_NUMBER",
    "US_SSN": "ID_NUMBER",
    "DATE_TIME": "DATE",
    "URL": "ID_NUMBER",
    "DE_TAX_ID": "TAX_ID",
    "DE_VAT_ID": "TAX_ID",
}


class PresidioDetector(Detector):
    name = "presidio"

    DEFAULT_ENTITIES: ClassVar[list[str]] = list(LABEL_MAP.keys())

    def __init__(self):
        # Defer import — analyzer load takes ~3s and we want fast cold start
        # for the FastAPI app.
        self._analyzer = None

    def _ensure_loaded(self):
        if self._analyzer is None:
            from presidio_analyzer import AnalyzerEngine

            self._analyzer = AnalyzerEngine()
            log.info("presidio analyzer loaded")
        return self._analyzer

    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectedSpan]:
        if not text:
            return []
        analyzer = self._ensure_loaded()
        results = analyzer.analyze(text=text, language="en", entities=self.DEFAULT_ENTITIES)
        out: list[DetectedSpan] = []
        for r in results:
            mapped = LABEL_MAP.get(r.entity_type)
            if mapped is None:
                continue
            value = text[r.start : r.end]
            out.append(
                DetectedSpan(
                    start=r.start,
                    end=r.end,
                    label=mapped,
                    value=value,
                    score=float(r.score),
                    detector=self.name,
                )
            )
        return out
