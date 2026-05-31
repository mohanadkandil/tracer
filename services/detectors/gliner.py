"""T2 — GLiNER multilingual PII NER. Zero-shot label set, supports batched inference.

When training/ has produced a fine-tuned checkpoint we swap the base model id for
the local path via env (GLINER_LOCAL_PATH). API stays the same.

Heavy. Loads on first call. ~200M params, runs CPU fine.
"""

from __future__ import annotations

import logging

from ..config import ENTITY_LABELS, GLINER_LOCAL_PATH, GLINER_MODEL_ID, T2_CONFIDENCE_THRESHOLD
from .base import DetectedSpan, Detector

log = logging.getLogger("detectors.gliner")


class GLiNERDetector(Detector):
    name = "gliner"

    def __init__(self, threshold: float = T2_CONFIDENCE_THRESHOLD):
        self._model = None
        self._labels = ENTITY_LABELS
        self.threshold = threshold

    def _ensure_loaded(self):
        if self._model is None:
            try:
                from gliner import GLiNER
            except ImportError:
                log.warning("gliner not installed — T2 will return empty spans. `uv sync --group serve` to enable.")
                return None
            model_id = GLINER_LOCAL_PATH or GLINER_MODEL_ID
            log.info("loading GLiNER: %s", model_id)
            try:
                if GLINER_LOCAL_PATH:
                    self._model = GLiNER.from_pretrained(model_id, local_files_only=True)
                else:
                    self._model = GLiNER.from_pretrained(model_id)
            except Exception:
                log.exception("GLiNER load failed; T2 disabled for this run")
                return None
        return self._model

    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectedSpan]:
        if not text.strip():
            return []
        model = self._ensure_loaded()
        if model is None:
            return []
        use_labels = labels or self._labels
        try:
            preds = model.predict_entities(text, use_labels, threshold=self.threshold)
        except Exception:
            log.exception("gliner predict failed")
            return []
        return [
            DetectedSpan(
                start=p["start"],
                end=p["end"],
                label=p["label"],
                value=p["text"],
                score=float(p["score"]),
                detector=self.name,
            )
            for p in preds
        ]

    def detect_batch(self, texts: list[str], labels: list[str] | None = None) -> list[list[DetectedSpan]]:
        """True batched inference if model supports it; else fall back to default loop."""
        if not texts:
            return []
        model = self._ensure_loaded()
        if model is None:
            return [[] for _ in texts]
        use_labels = labels or self._labels
        # Some gliner versions expose batch_predict_entities; fall back if not.
        batch_fn = getattr(model, "batch_predict_entities", None)
        if batch_fn is None:
            return super().detect_batch(texts, labels)
        try:
            batched = batch_fn(texts, use_labels, threshold=self.threshold)
        except Exception:
            log.exception("gliner batch predict failed; falling back to loop")
            return super().detect_batch(texts, labels)
        return [
            [
                DetectedSpan(
                    start=p["start"],
                    end=p["end"],
                    label=p["label"],
                    value=p["text"],
                    score=float(p["score"]),
                    detector=self.name,
                )
                for p in preds
            ]
            for preds in batched
        ]
