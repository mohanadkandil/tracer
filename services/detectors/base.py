"""Detector contract. Same shape for every tier so routing can fan out cleanly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class DetectedSpan:
    start: int
    end: int
    label: str
    value: str
    score: float
    detector: str


class Detector(ABC):
    name: str

    @abstractmethod
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectedSpan]:
        """Return spans in `text`. `labels` is a hint, detectors may ignore it."""
        ...

    def detect_batch(self, texts: list[str], labels: list[str] | None = None) -> list[list[DetectedSpan]]:
        """Default = loop. Subclasses can override for true batching."""
        return [self.detect(t, labels) for t in texts]
