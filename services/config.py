"""Runtime configuration. Env-driven, sane defaults for hackathon demo."""

from __future__ import annotations

import os
from pathlib import Path

# Detection thresholds
T2_CONFIDENCE_THRESHOLD: float = float(os.environ.get("T2_THRESHOLD", "0.5"))
T3_ESCALATION_THRESHOLD: float = float(os.environ.get("T3_THRESHOLD", "0.6"))

# Models
GLINER_MODEL_ID: str = os.environ.get("GLINER_MODEL", "urchade/gliner_multi_pii-v1")
GLINER_LOCAL_PATH: str | None = os.environ.get("GLINER_LOCAL_PATH")
REASONER_KIND: str = os.environ.get("REASONER", "mock")  # mock | lfm2 | openrouter

# Entity labels we care about (passed to GLiNER as zero-shot label set)
ENTITY_LABELS: list[str] = [
    "PERSON",
    "EMPLOYEE_ID",
    "EMAIL",
    "PHONE",
    "ADDRESS",
    "TAX_ID",
    "IBAN",
    "DEPARTMENT",
    "COMPANY",
    "DATE",
    "ID_NUMBER",
    "SIGNATURE",
    "USERNAME",
]

# Storage — defaults work for local + Railway (mount volume at /app/data)
DB_PATH: Path = Path(os.environ.get("DB_PATH", "data/scan.db"))
# Where rendered PDFs / demo files live for the FileSystem connector
# In prod set this to a volume path; local stays at data/files/

# Workers
WORKER_COUNT: int = int(os.environ.get("WORKERS", "4"))
QUEUE_MAX_SIZE: int = int(os.environ.get("QUEUE_MAX", "1024"))

# Demo data
DEMO_FILES_ROOT: Path = Path(os.environ.get("DEMO_ROOT", "data/files"))

# CORS — Next.js dev server + production Vercel domain(s)
# Set CORS_ORIGINS as comma-separated list in prod. Use "*" only for demos.
CORS_ORIGINS: list[str] = [
    o.strip() for o in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",") if o.strip()
]

# Regex allowlist for preview deployments (Vercel gives unique URLs per push)
CORS_ORIGIN_REGEX: str | None = os.environ.get("CORS_ORIGIN_REGEX")
