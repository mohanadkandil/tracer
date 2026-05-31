"""Render labeled JSONL examples into real files (PDF / DOCX / TXT / EML).

Labels are stripped from the output — the model has to find PII blind. Ground truth
is saved as a sidecar JSONL keyed by file path so we can score model output later.

Usage:
  uv run python -m data_gen.render --in data/out/test.jsonl --out data/files
  uv run python -m data_gen.render --in data/out/test.jsonl --out data/files \
      --formats pdf,docx,txt,eml --pdf-ratio 0.5 --docx-ratio 0.3 --eml-ratio 0.1
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import orjson
from docx import Document
from faker import Faker
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .schemas import Example, Lang

FAKERS = {"de": Faker("de_DE"), "en": Faker("en_US")}


# Bosch-like dept folder taxonomy. Used to give each file a realistic SharePoint path.
DEPT_FOLDERS = {
    "expense": "Finance",
    "it_access": "IT",
    "incident": "Compliance",
    "supplier": "Procurement",
    "training": "HR",
    "policy": "Compliance",
    "meeting": "General",
    "blank_template": "Templates",
}


@dataclass
class FormatMix:
    pdf: float = 0.5
    docx: float = 0.3
    txt: float = 0.1
    eml: float = 0.1

    def pick(self, rng: random.Random) -> str:
        r = rng.random()
        acc = 0.0
        for fmt, w in [("pdf", self.pdf), ("docx", self.docx), ("txt", self.txt), ("eml", self.eml)]:
            acc += w
            if r <= acc:
                return fmt
        return "pdf"


# ---------- renderers ----------


def render_pdf(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    flow = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            flow.append(Spacer(1, 6))
            continue
        # Escape ampersands/lt/gt for ReportLab XML mini-lang
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        flow.append(Paragraph(safe, body))
    doc.build(flow)


def render_docx(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(str(path))


def render_txt(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_eml(text: str, path: Path, lang: Lang, doc_type: str, rng: random.Random) -> None:
    """Wrap body in minimal RFC 5322 envelope."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fake = FAKERS[lang]
    sender = fake.company_email()
    recipient = fake.company_email()
    if lang == "de":
        subject_map = {
            "expense": "Spesenabrechnung zur Prüfung",
            "it_access": "IT-Zugriffsanfrage",
            "incident": "Vorfallsmeldung",
            "supplier": "Lieferantenanlage",
            "training": "Schulungsbestätigung",
        }
        subject = subject_map.get(doc_type, "Dokument zur Kenntnisnahme")
    else:
        subject_map = {
            "expense": "Expense report for review",
            "it_access": "IT access request",
            "incident": "Incident report",
            "supplier": "Supplier onboarding",
            "training": "Training confirmation",
        }
        subject = subject_map.get(doc_type, "Document for your attention")

    eml = (
        f"From: {sender}\r\n"
        f"To: {recipient}\r\n"
        f"Subject: {subject}\r\n"
        f"Date: {fake.date_time_this_year().strftime('%a, %d %b %Y %H:%M:%S +0000')}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{text}\r\n"
    )
    path.write_text(eml, encoding="utf-8")


# ---------- pipeline ----------


def _iter_jsonl(path: Path) -> Iterable[Example]:
    with path.open("rb") as f:
        for line in f:
            if not line.strip():
                continue
            yield Example.model_validate(orjson.loads(line))


def _safe_filename(doc_type: str, lang: Lang, ex_id: str, ext: str) -> str:
    return f"{doc_type}_{lang}_{ex_id}.{ext}"


def render_all(
    in_path: Path,
    out_root: Path,
    formats: list[str],
    mix: FormatMix,
    seed: int = 42,
) -> dict[str, int]:
    rng = random.Random(seed)
    truth_path = out_root / "_truth.jsonl"
    out_root.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {"pdf": 0, "docx": 0, "txt": 0, "eml": 0, "total": 0}

    with truth_path.open("wb") as truth_f:
        for ex in _iter_jsonl(in_path):
            fmt = mix.pick(rng)
            if fmt not in formats:
                # fall back to first allowed
                fmt = formats[0]
            folder = DEPT_FOLDERS.get(ex.doc_type, "General")
            file_path = out_root / folder / _safe_filename(ex.doc_type, ex.lang, ex.id, fmt)

            if fmt == "pdf":
                render_pdf(ex.text, file_path)
            elif fmt == "docx":
                render_docx(ex.text, file_path)
            elif fmt == "txt":
                render_txt(ex.text, file_path)
            elif fmt == "eml":
                render_eml(ex.text, file_path, ex.lang, ex.doc_type, rng)

            counts[fmt] += 1
            counts["total"] += 1

            rel = file_path.relative_to(out_root).as_posix()
            truth_record = {
                "file": rel,
                "doc_type": ex.doc_type,
                "lang": ex.lang,
                "format": fmt,
                "source_id": ex.id,
                "text": ex.text,
                "entities": [e.model_dump() for e in ex.entities],
            }
            truth_f.write(orjson.dumps(truth_record))
            truth_f.write(b"\n")

    return counts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", required=True, help="Input JSONL (train/val/test)")
    p.add_argument("--out", dest="out_path", default="data/files")
    p.add_argument("--formats", default="pdf,docx,txt,eml", help="Comma-separated subset to enable")
    p.add_argument("--pdf-ratio", type=float, default=0.5)
    p.add_argument("--docx-ratio", type=float, default=0.3)
    p.add_argument("--txt-ratio", type=float, default=0.1)
    p.add_argument("--eml-ratio", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    mix = FormatMix(pdf=args.pdf_ratio, docx=args.docx_ratio, txt=args.txt_ratio, eml=args.eml_ratio)

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    counts = render_all(in_path, out_path, formats, mix, seed=args.seed)

    print(f"Rendered → {out_path}/")
    for k in ("pdf", "docx", "txt", "eml"):
        print(f"  .{k:4s}  {counts[k]}")
    print(f"  total {counts['total']}")
    print(f"Ground truth: {out_path / '_truth.jsonl'}")


if __name__ == "__main__":
    main()
