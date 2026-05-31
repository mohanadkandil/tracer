"""Bytes → text. Supports PDF, DOCX, EML, TXT. Soft-fails on unknown formats."""

from __future__ import annotations

import email
import email.policy
import io
from pathlib import Path

import pypdf
from docx import Document


def extract_text(data: bytes, hint_path: str | None = None) -> str:
    """Best-effort text extraction. Hint comes from path/MIME, used to pick a parser."""
    suffix = Path(hint_path).suffix.lower() if hint_path else ""

    if suffix == ".pdf":
        return _from_pdf(data)
    if suffix in {".docx"}:
        return _from_docx(data)
    if suffix == ".eml":
        return _from_eml(data)
    if suffix in {".txt", ".md", ""}:
        return data.decode("utf-8", errors="replace")
    # last resort
    return data.decode("utf-8", errors="replace")


def _from_pdf(data: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:
        return ""


def _from_docx(data: bytes) -> str:
    try:
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def _from_eml(data: bytes) -> str:
    try:
        msg = email.message_from_bytes(data, policy=email.policy.default)
        header = "\n".join(
            f"{k}: {v}" for k, v in msg.items() if k.lower() in {"from", "to", "subject", "date"}
        )
        body_part = msg.get_body(preferencelist=("plain", "html"))
        body = body_part.get_content() if body_part else ""
        return f"{header}\n\n{body}"
    except Exception:
        return data.decode("utf-8", errors="replace")
