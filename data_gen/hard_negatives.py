"""Generate hard-negative docs: business content that LOOKS like it might have PII but doesn't.

Two sources:
1. Local: rule-based generic policy/SOP/agenda text, no real names.
2. Remote: OpenRouter LLM gen with strict 'no PII' instruction + post-filter via regex.

We post-filter every output through a quick PII regex sweep — anything that looks like
email/IBAN/tax-id/phone is rejected to keep negatives clean.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import uuid
from typing import Iterable

import httpx
from tqdm.asyncio import tqdm_asyncio

from .schemas import Example, Lang

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

NEG_SYS = (
    "You generate realistic corporate document fragments (policies, meeting agendas, SOPs, training outlines, "
    "process descriptions). STRICT: do NOT include any real or invented personal data — no names of people, "
    "no email addresses, no phone numbers, no postal addresses, no employee or tax IDs, no IBAN, no signatures. "
    "Refer to people only by generic roles ('the team lead', 'the auditor', 'the approver'). "
    "Output ONLY the document body, no preamble."
)

NEG_TOPICS_EN = [
    "GDPR data retention policy overview",
    "Quarterly compliance meeting agenda",
    "Standard operating procedure for incident triage",
    "Information security awareness training outline",
    "Vendor risk assessment process description",
    "Change management workflow documentation",
    "Code of conduct summary",
    "Travel reimbursement policy guidelines",
    "Internal audit checklist (no findings)",
    "Cybersecurity reporting framework",
]
NEG_TOPICS_DE = [
    "Übersicht der Aufbewahrungsrichtlinie nach DSGVO",
    "Quartalsweise Compliance-Sitzungsagenda",
    "Standardvorgehen zur Vorfalls-Triage",
    "Schulungsumriss zur Informationssicherheits-Sensibilisierung",
    "Prozessbeschreibung Lieferantenrisikobewertung",
    "Dokumentation des Änderungsmanagement-Workflows",
    "Zusammenfassung des Verhaltenskodex",
    "Richtlinien zur Reisekostenerstattung",
    "Interne Audit-Checkliste (ohne Befund)",
    "Rahmenwerk für Cybersicherheitsmeldungen",
]

PII_REGEX = re.compile(
    r"(?:[A-Z][a-zäöüß]+\s+[A-Z][a-zäöüß]+)"  # rough person name FirstLast (cap-cap)
    r"|(?:[\w.+-]+@[\w-]+\.[\w.-]+)"  # email
    r"|(?:\bDE\d{9}\b)"  # tax id
    r"|(?:\bVAT\d{9}\b)"
    r"|(?:\bE-\d{5}\b)"  # employee id
    r"|(?:\+?\d[\d\s().-]{7,}\d)"  # phone
    r"|(?:\bDE\d{20}\b)",  # IBAN-like
    flags=re.UNICODE,
)


def _has_pii_like(text: str) -> bool:
    # Permit lone capitalized words common in titles; only reject obvious matches
    if PII_REGEX.search(text):
        return True
    return False


def _new_id() -> str:
    return f"neg-{uuid.uuid4().hex[:8]}"


# ---------- local rule-based negatives ----------

POLICY_PARAS_EN = [
    "Personal data must be retained only for the duration necessary to fulfill the purpose for which it was collected.",
    "All staff are required to complete annual data protection awareness training before accessing customer systems.",
    "Access requests must follow the principle of least privilege and undergo quarterly recertification.",
    "Records relating to ongoing investigations should be marked confidential and stored in restricted repositories.",
    "Risk assessments must be repeated when material changes to processing activities occur.",
    "Vendor due diligence must include verification of certifications and a written subprocessor list.",
]
POLICY_PARAS_DE = [
    "Personenbezogene Daten dürfen nur so lange aufbewahrt werden, wie dies für den Erhebungszweck erforderlich ist.",
    "Alle Mitarbeitenden müssen jährlich an einer Datenschutz-Sensibilisierungsschulung teilnehmen.",
    "Zugriffsanfragen folgen dem Prinzip der minimalen Berechtigung und werden quartalsweise rezertifiziert.",
    "Unterlagen zu laufenden Ermittlungen sind als vertraulich zu kennzeichnen und in beschränkten Ablagen aufzubewahren.",
    "Risikobewertungen sind bei wesentlichen Änderungen der Verarbeitungstätigkeiten zu wiederholen.",
    "Die Lieferantenprüfung umfasst die Verifikation der Zertifizierungen sowie eine schriftliche Subunternehmerliste.",
]


def gen_local_negative(lang: Lang) -> Example:
    paras = POLICY_PARAS_DE if lang == "de" else POLICY_PARAS_EN
    n = random.randint(2, 4)
    body = "\n\n".join(random.sample(paras, n))
    title = "Richtlinie zur Datenaufbewahrung" if lang == "de" else "Data Retention Policy"
    text = f"{title}\n\n{body}\n"
    return Example(
        id=_new_id(),
        doc_type="policy",
        lang=lang,
        is_template=False,
        is_filled=True,
        source="hard_negative",
        text=text,
        entities=[],
    )


def generate_local_negatives(n: int, lang_ratio_de: float = 0.5, seed: int = 44) -> list[Example]:
    rng = random.Random(seed)
    out: list[Example] = []
    for _ in range(n):
        lang: Lang = "de" if rng.random() < lang_ratio_de else "en"
        out.append(gen_local_negative(lang))
    return out


# ---------- LLM-generated negatives ----------


async def _call_negative(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    lang: Lang,
    topic: str,
    sem: asyncio.Semaphore,
) -> Example | None:
    user = (
        f"Write a short ({random.randint(120, 220)}-word) corporate document in {'German' if lang == 'de' else 'English'} "
        f"on the topic: '{topic}'. Remember: no personal data of any kind."
    )
    async with sem:
        try:
            r = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/bosch-gdpr-hackathon",
                    "X-Title": "Bosch GDPR negatives gen",
                },
                json={
                    "model": model,
                    "temperature": 0.8,
                    "max_tokens": 600,
                    "messages": [
                        {"role": "system", "content": NEG_SYS},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=60.0,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    if _has_pii_like(text):
        return None

    doc_type = "meeting" if "agenda" in topic.lower() or "sitzung" in topic.lower() else "policy"
    return Example(
        id=_new_id(),
        doc_type=doc_type,
        lang=lang,
        is_template=False,
        is_filled=True,
        source="hard_negative",
        text=text,
        entities=[],
    )


async def generate_llm_negatives(
    n: int,
    lang_ratio_de: float = 0.5,
    api_key: str | None = None,
    model: str | None = None,
    concurrency: int = 8,
    seed: int = 45,
) -> list[Example]:
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    model = model or os.environ.get("OPENROUTER_NEGATIVES_MODEL", "meta-llama/llama-3.3-70b-instruct")

    rng = random.Random(seed)
    plans: list[tuple[Lang, str]] = []
    for _ in range(n):
        lang: Lang = "de" if rng.random() < lang_ratio_de else "en"
        topic = rng.choice(NEG_TOPICS_DE if lang == "de" else NEG_TOPICS_EN)
        plans.append((lang, topic))

    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        tasks = [_call_negative(client, api_key, model, lang, topic, sem) for lang, topic in plans]
        results = await tqdm_asyncio.gather(*tasks, desc="hard_negatives")
    return [r for r in results if r is not None]
