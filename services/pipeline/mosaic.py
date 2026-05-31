"""Mosaic: link weak PII fragments across documents back to a single identity.

Three layers, additive:

  L1 — entity identity graph
        For each scanned doc, every PERSON span is connected to every co-occurring
        EMPLOYEE_ID / EMAIL / PHONE in the same doc. Stored as edges in
        `entity_links`. Lets us answer: "all identifiers we know for Hans Müller".

  L2 — canonicalization
        Name strings ("H. Müller", "Hans Müller", "Müller, Hans") collapse to a
        single canonical key. Match on canonical, not surface form.

  L3 — embedding mosaic
        Each PERSON span gets a vector built from a small context window. Cosine
        similarity > 0.85 → same person likely, even when names look different
        ("Hans M. (Entwicklung)" ↔ "Hans Müller, Forschung"). Multilingual model,
        local CPU inference.

The three are wired together: `link_finding` writes both the canonical entry
(L1+L2) and, if the embedder is available, the vector (L3). Queries fall back
gracefully when L3 isn't available.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import struct
from dataclasses import dataclass
from typing import Iterable

from ..db import get_conn
from ..schemas import Span

log = logging.getLogger("pipeline.mosaic")

# Stoplist of common German / English corporate form labels that GLiNER zero-shot
# often misclassifies as PERSON. Per-token check (any token match → reject).
_PERSON_STOPWORDS = {
    # German articles / determiners
    "die", "der", "das", "den", "dem", "des", "ein", "eine", "einen", "einer", "eines",
    # English articles
    "the", "a", "an", "of", "for", "to", "on",
    # Titles / honorifics (NOT names by themselves)
    "mr", "mrs", "ms", "dr", "prof", "frau", "herr",
    # German form labels (singulars + common variants)
    "pflege", "begründung", "begrundung", "genehmigung", "zugriff", "zugriffsebene",
    "abteilung", "vorgesetzte", "vorgesetzter", "datum", "unterschrift", "kommentare",
    "antrag", "antragsteller", "ausgefüllt", "prüfung", "entscheidung", "system",
    "mitarbeiter", "mitarbeiterin", "name", "kategorie", "betrag", "beschreibung",
    "kurs", "ergebnis", "status", "dozent", "teilnehmer", "teilnehmerin",
    "vorfallsmeldung", "spesenabrechnung", "lieferantenanlage", "schulungsbewertung",
    "purpose", "review", "approval", "approver", "comments", "manager", "department",
    "summary", "engineering", "eng", "data", "code", "passed", "failed", "approved",
    "rejected", "genehmigt", "abgelehnt", "bedingt", "owner", "deadline", "frist",
    "verantwortlich", "instructor", "participant", "course", "score",
    # Specific labels we saw leak in earlier scans
    "firma", "steuernummer", "telefon", "zertifizierung", "ansprechpartner",
    "risikostufe", "iban", "zweck", "rolle", "rollen", "erfassten", "erfasste",
    "bearbeiter", "verteiler", "datenverarbeitung", "datenschutz", "maßnahme",
    "massnahme", "empfängergruppe", "empfänger", "rahmen", "projektdokumentation",
    "bahnticket", "lead", "governance", "false", "falsche", "auswahl",
}

# Words used in compound German-noun phrases that must reject the whole span.
# If any of these substrings appear in a span's lowercase form → reject.
_REJECT_SUBSTRINGS = (
    "begründ", "begrund", "abteil", "genehmig", "unterschrift", "antrag",
    "steuer", "firma", "kosten", "zertifiz", "verteil", "empfäng", "massnahm",
    "maßnahm", "rahmen ", "ticket", "verarbeit", "kontroll", "auswahl",
)

# Whitelist: common European first names. Used only as a positive signal for
# borderline cases — not required (allows realistic-looking but unfamiliar names).
_COMMON_FIRST_NAMES = {
    # German
    "hans", "anna", "tobias", "elena", "jonas", "miriam", "philipp", "sara",
    "klaus", "ute", "stefan", "katja", "michael", "lisa", "thomas", "petra",
    "andreas", "monika", "wolfgang", "ingrid", "jürgen", "brigitte", "uwe",
    "maike", "matthias", "claudia", "ralf", "susanne", "frank", "birgit",
    # English
    "john", "mary", "david", "sarah", "michael", "jessica", "kenneth", "linda",
    "robert", "patricia", "james", "jennifer", "william", "elizabeth", "richard",
    "barbara", "joseph", "susan", "thomas", "karen", "charles", "nancy",
}


def _is_false_person(value: str) -> bool:
    """Reject a PERSON span unless it looks like a real first+last name.

    Rules:
      1. Length 4-50 chars.
      2. 2-4 tokens.
      3. No token in stoplist (articles, form labels, common German nouns).
      4. Each token must be alpha-only, ≥2 chars, start with uppercase.
      5. Reject if any substring matches a German compound-noun pattern.
      6. Reject if it contains ':' or digits.
    """
    v = value.strip()
    if len(v) < 4 or len(v) > 50:
        return True
    if ":" in v or any(ch.isdigit() for ch in v):
        return True

    low = v.lower()
    for sub in _REJECT_SUBSTRINGS:
        if sub in low:
            return True

    tokens = v.split()
    if not (2 <= len(tokens) <= 4):
        return True

    for tok in tokens:
        norm = tok.strip(".,;:-").lower()
        if not norm:
            return True
        if norm in _PERSON_STOPWORDS:
            return True
        if len(norm) < 2:
            return True
        # All-alpha (allow unicode letters, hyphens, apostrophes)
        if not all(c.isalpha() or c in "-'" for c in norm):
            return True
        # Must start with uppercase letter (after stripping leading punct)
        cleaned = tok.lstrip(".,;:-")
        if not cleaned or not cleaned[0].isupper():
            return True

    return False


# Labels we treat as person identifiers (linkable to a canonical person)
PERSON_LABELS = {"PERSON"}
ID_LABELS = {"EMPLOYEE_ID", "EMAIL", "PHONE", "USERNAME", "SIGNATURE"}
LINKABLE_LABELS = PERSON_LABELS | ID_LABELS

# Context window in chars around a PERSON span used to build the embedding
EMBEDDING_CONTEXT_CHARS = 120
SIMILARITY_THRESHOLD = 0.85


# ---------- L2: canonicalization ----------

_HONORIFICS = {"mr", "mrs", "ms", "dr", "prof", "herr", "frau"}
_PUNCT_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def canonical_person(name: str) -> str:
    """Collapse a name to a stable key.

    Examples:
        "Hans Müller"      → "mueller-hans"
        "Müller, Hans"     → "mueller-hans"
        "H. Müller"        → "mueller-h"    (single-letter first name kept as initial)
        "Dr. Hans Müller"  → "mueller-hans"
        "MÜLLER HANS"      → "mueller-hans"
    """
    s = name.strip().lower()
    # Strip honorifics
    s = re.sub(r"\b(" + "|".join(_HONORIFICS) + r")\.?\s+", "", s)
    # Strip punctuation except hyphens (keep multi-part names: "Jean-Marc")
    s = _PUNCT_RE.sub("", s)
    s = _ascii_fold(s)
    # Normalize "lastname, firstname" → "firstname lastname"
    if "," in name:
        parts = [p.strip() for p in name.split(",") if p.strip()]
        if len(parts) == 2:
            s = f"{parts[1].lower()} {parts[0].lower()}"
            s = _PUNCT_RE.sub("", _ascii_fold(s))
    parts = _WS_RE.split(s.strip())
    if not parts:
        return s
    if len(parts) == 1:
        return parts[0]
    first, *rest = parts
    last = rest[-1]
    return f"{last}-{first}"


def canonical_identifier(label: str, value: str) -> str:
    """Canonical key for non-name identifiers — preserve the exact value but lowercased."""
    v = value.strip().lower()
    return f"{label.lower()}:{v}"


def _ascii_fold(s: str) -> str:
    """Best-effort ASCII fold for European diacritics (no external dep)."""
    table = str.maketrans(
        {
            "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
            "Ä": "ae", "Ö": "oe", "Ü": "ue",
            "à": "a", "á": "a", "â": "a", "ã": "a",
            "è": "e", "é": "e", "ê": "e", "ë": "e",
            "ì": "i", "í": "i", "î": "i", "ï": "i",
            "ò": "o", "ó": "o", "ô": "o", "õ": "o",
            "ù": "u", "ú": "u", "û": "u",
            "ñ": "n", "ç": "c",
        }
    )
    return s.translate(table)


# ---------- L1: identity graph ----------


@dataclass(slots=True)
class IdentityHit:
    canonical: str
    value: str
    label: str
    file_path: str
    file_id: str
    owner: str | None
    finding_id: int | None


def link_findings_for_doc(
    file_id: str,
    file_path: str,
    owner: str | None,
    text: str,
    spans: Iterable[Span],
    finding_ids: dict[tuple[int, int, str], int] | None = None,
) -> int:
    """Build L1 + L2 entries for a single scanned doc.

    For each PERSON span we record one row per co-occurring identifier in the same
    doc (or just itself if no identifiers are nearby). For each non-PERSON
    identifier we record one row tying it to every PERSON in the doc.

    Returns the number of edges written.
    """
    spans = list(spans)
    if not spans:
        return 0

    people: list[Span] = [s for s in spans if s.label in PERSON_LABELS and not _is_false_person(s.value)]
    ids: list[Span] = [s for s in spans if s.label in ID_LABELS]

    # If nothing linkable, skip
    if not people and not ids:
        return 0

    person_keys = [(canonical_person(p.value), p.value) for p in people]
    id_keys = [(canonical_identifier(i.label, i.value), i.value, i.label) for i in ids]

    finding_ids = finding_ids or {}
    rows: list[tuple] = []

    # Person node: one self row per person, plus one row per linked identifier
    for p_canon, p_val in person_keys:
        rows.append((p_canon, p_val, "PERSON", file_id, file_path,
                     finding_ids.get((-1, -1, p_val)), owner, p_canon))
        for i_canon, i_val, i_label in id_keys:
            rows.append((p_canon, i_val, i_label, file_id, file_path,
                         finding_ids.get((-1, -1, i_val)), owner, p_canon))
            rows.append((i_canon, i_val, i_label, file_id, file_path,
                         finding_ids.get((-1, -1, i_val)), owner, p_canon))

    # Orphan identifiers (no PERSON in this doc) — link to themselves
    if not people:
        for i_canon, i_val, i_label in id_keys:
            rows.append((i_canon, i_val, i_label, file_id, file_path,
                         finding_ids.get((-1, -1, i_val)), owner, None))

    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO entity_links (canonical, value, label, file_id, file_path, finding_id, owner, co_canonical) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    # L3 — embeddings (only PERSON spans, async-friendly best-effort)
    embedder = get_embedder()
    if embedder is not None and people:
        try:
            ctx_inputs = [(p, _context_window(text, p)) for p in people]
            vectors = embedder.encode([c for _, c in ctx_inputs])
            with get_conn() as conn:
                for (span, _ctx), vec in zip(ctx_inputs, vectors):
                    canon = canonical_person(span.value)
                    fid = finding_ids.get((span.start, span.end, span.value), -1)
                    conn.execute(
                        "INSERT OR REPLACE INTO entity_embeddings "
                        "(finding_id, canonical, value, file_id, file_path, vector, dim) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            fid if fid >= 0 else hash((file_id, span.start, span.end)) % (10**9),
                            canon,
                            span.value,
                            file_id,
                            file_path,
                            _pack_vector(vec),
                            len(vec),
                        ),
                    )
        except Exception:
            log.exception("embedding write failed; mosaic L3 partial for %s", file_path)

    return len(rows)


def _context_window(text: str, span: Span) -> str:
    half = EMBEDDING_CONTEXT_CHARS // 2
    return text[max(0, span.start - half) : span.end + half]


# ---------- L3: embeddings ----------


_embedder_singleton = None


def get_embedder():
    """Lazy-load sentence-transformers. Returns None if unavailable."""
    global _embedder_singleton
    if _embedder_singleton is False:
        return None
    if _embedder_singleton is not None:
        return _embedder_singleton
    try:
        from sentence_transformers import SentenceTransformer

        model_id = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        log.info("loading embedder: %s", model_id)
        _embedder_singleton = SentenceTransformer(model_id)
        return _embedder_singleton
    except Exception:
        log.warning("sentence-transformers not available; mosaic runs L1+L2 only")
        _embedder_singleton = False
        return None


def _pack_vector(vec) -> bytes:
    """Pack a numeric iterable into a compact bytes blob (float32 little-endian)."""
    return struct.pack(f"<{len(vec)}f", *map(float, vec))


def _unpack_vector(blob: bytes, dim: int) -> list[float]:
    return list(struct.unpack(f"<{dim}f", blob))


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ---------- queries ----------


@dataclass(slots=True)
class PersonIdentity:
    canonical: str
    display_name: str
    files: list[str]
    identifiers: dict[str, set[str]]  # label → values
    fuzzy_matches: list[tuple[str, str, float]]  # (other_canonical, value, similarity)
    re_id_risk: str  # "low" | "medium" | "high" | "critical"
    risk_factors: list[str]


def lookup_person(query: str, fuzzy: bool = True) -> PersonIdentity | None:
    """Return everything we know about a person.

    Steps:
      1. Canonicalize the query.
      2. Pull L1 exact-match rows.
      3. Compute fuzzy matches via L3 embeddings (if available).
      4. Aggregate identifiers + files.
      5. Score re-id risk based on identifier diversity + file spread.
    """
    canon = canonical_person(query)

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT canonical, value, label, file_id, file_path, owner "
            "FROM entity_links WHERE canonical = ? OR co_canonical = ?",
            (canon, canon),
        ).fetchall()

    if not rows:
        # try a softer match: last name only
        last = canon.split("-")[0]
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT canonical, value, label, file_id, file_path, owner "
                "FROM entity_links WHERE canonical LIKE ? OR co_canonical LIKE ?",
                (f"{last}-%", f"{last}-%"),
            ).fetchall()

    if not rows:
        return None

    identifiers: dict[str, set[str]] = {}
    files: set[str] = set()
    display_name = query
    for r in rows:
        identifiers.setdefault(r["label"], set()).add(r["value"])
        files.add(r["file_path"])
        if r["label"] == "PERSON":
            # prefer longest observed surface form as display
            if len(r["value"]) > len(display_name):
                display_name = r["value"]

    # L3 fuzzy expansion
    fuzzy_matches: list[tuple[str, str, float]] = []
    if fuzzy:
        fuzzy_matches = _fuzzy_neighbors(canon)
        for other_canon, _other_val, _sim in fuzzy_matches:
            with get_conn() as conn:
                more = conn.execute(
                    "SELECT label, value, file_path FROM entity_links "
                    "WHERE canonical = ? OR co_canonical = ?",
                    (other_canon, other_canon),
                ).fetchall()
            for r in more:
                identifiers.setdefault(r["label"], set()).add(r["value"])
                files.add(r["file_path"])

    risk, factors = _score_risk(identifiers, files)

    return PersonIdentity(
        canonical=canon,
        display_name=display_name,
        files=sorted(files),
        identifiers={k: sorted(v) for k, v in identifiers.items()},  # type: ignore[misc]
        fuzzy_matches=fuzzy_matches,
        re_id_risk=risk,
        risk_factors=factors,
    )


def _fuzzy_neighbors(canonical: str, top_k: int = 5) -> list[tuple[str, str, float]]:
    """Find canonical names similar to this one via embedding cosine similarity."""
    with get_conn() as conn:
        seed_rows = conn.execute(
            "SELECT vector, dim FROM entity_embeddings WHERE canonical = ? LIMIT 1",
            (canonical,),
        ).fetchall()
        if not seed_rows:
            return []
        seed_vec = _unpack_vector(seed_rows[0]["vector"], seed_rows[0]["dim"])
        all_rows = conn.execute(
            "SELECT canonical, value, vector, dim FROM entity_embeddings WHERE canonical != ?",
            (canonical,),
        ).fetchall()

    scored: dict[str, tuple[str, float]] = {}
    for r in all_rows:
        other = _unpack_vector(r["vector"], r["dim"])
        sim = _cosine(seed_vec, other)
        if sim < SIMILARITY_THRESHOLD:
            continue
        # keep best per other-canonical
        existing = scored.get(r["canonical"])
        if existing is None or sim > existing[1]:
            scored[r["canonical"]] = (r["value"], sim)
    ranked = sorted(scored.items(), key=lambda kv: -kv[1][1])[:top_k]
    return [(c, v, sim) for c, (v, sim) in ranked]


def _score_risk(identifiers: dict[str, set[str]], files: set[str]) -> tuple[str, list[str]]:
    factors: list[str] = []
    distinct_id_types = sum(1 for k, v in identifiers.items() if k != "PERSON" and v)
    n_files = len(files)
    if distinct_id_types >= 3:
        factors.append(f"{distinct_id_types} distinct identifier types linked (name + emp ID + email + ...)")
    if n_files >= 5:
        factors.append(f"appears across {n_files} files — broad exposure surface")
    if "EMPLOYEE_ID" in identifiers and "ADDRESS" in identifiers:
        factors.append("employee ID + home address co-located — high re-identification risk")
    if "TAX_ID" in identifiers:
        factors.append("regulated identifier present (tax ID)")

    if distinct_id_types >= 3 and n_files >= 5:
        return "critical", factors
    if distinct_id_types >= 2 and n_files >= 3:
        return "high", factors
    if distinct_id_types >= 1:
        return "medium", factors
    return "low", factors


def build_graph(limit_people: int = 50) -> dict:
    """Return a force-directed graph payload: nodes + edges.

    Nodes = unique canonicals across both `entity_links.canonical` and `co_canonical`.
    Edges = entity_links rows where canonical != co_canonical (a connection between
    two entities in the same doc).
    """
    with get_conn() as conn:
        # Top N most-connected persons first
        top = conn.execute(
            "SELECT canonical, COUNT(DISTINCT file_id) AS docs FROM entity_links "
            "WHERE canonical = co_canonical AND label = 'PERSON' "
            "GROUP BY canonical ORDER BY docs DESC LIMIT ?",
            (limit_people,),
        ).fetchall()
        top_canonicals = {r["canonical"] for r in top}

        if not top_canonicals:
            return {"nodes": [], "edges": []}

        rows = conn.execute(
            "SELECT canonical, value, label, file_path, co_canonical "
            "FROM entity_links WHERE co_canonical IN ({}) OR canonical IN ({})".format(
                ",".join("?" * len(top_canonicals)),
                ",".join("?" * len(top_canonicals)),
            ),
            (*top_canonicals, *top_canonicals),
        ).fetchall()

    nodes_index: dict[str, dict] = {}
    edges: list[dict] = []
    for r in rows:
        canon = r["canonical"]
        # Filter junk PERSON values that were stored before the filter existed
        if r["label"] == "PERSON" and _is_false_person(r["value"]):
            continue
        if canon not in nodes_index:
            nodes_index[canon] = {
                "id": canon,
                "label": r["label"],
                "value": r["value"],
                "docs": 0,
            }
        nodes_index[canon]["docs"] += 1
        if r["co_canonical"] and r["co_canonical"] != canon:
            # Skip edges whose other end was a junk PERSON
            edges.append({
                "source": r["co_canonical"],
                "target": canon,
                "file": r["file_path"],
            })

    return {"nodes": list(nodes_index.values()), "edges": edges}
