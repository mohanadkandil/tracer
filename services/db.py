"""SQLite schema + thin connection helper.

Schema mirrors what Postgres would look like at scale, so a switch is a string change.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    path            TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    bytes           INTEGER,
    mime            TEXT,
    owner           TEXT,
    last_seen       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, path)
);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_owner ON files(owner);

CREATE TABLE IF NOT EXISTS scan_seen (
    content_hash    TEXT PRIMARY KEY,
    last_scanned    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    spans_json      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id         TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    label           TEXT NOT NULL,
    value           TEXT NOT NULL,
    score           REAL NOT NULL,
    severity        TEXT NOT NULL,
    owner           TEXT,
    detector        TEXT NOT NULL,
    span_start      INTEGER NOT NULL,
    span_end        INTEGER NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_findings_file ON findings(file_id);
CREATE INDEX IF NOT EXISTS idx_findings_owner ON findings(owner);
CREATE INDEX IF NOT EXISTS idx_findings_label ON findings(label);

CREATE TABLE IF NOT EXISTS dsar_requests (
    id              TEXT PRIMARY KEY,
    subject         TEXT NOT NULL,
    requester_email TEXT,
    article         TEXT NOT NULL DEFAULT '17',
    source          TEXT NOT NULL,         -- 'web' | 'api' | 'slack' | 'email' | 'webhook'
    raw_email       TEXT,                  -- original message body
    identifiers_json TEXT NOT NULL,        -- parsed identifier list
    status          TEXT NOT NULL DEFAULT 'pending', -- pending | approved | declined | executed
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decided_at      TIMESTAMP,
    decided_by      TEXT,
    decision_note   TEXT,
    files_processed INTEGER DEFAULT 0,
    findings_erased INTEGER DEFAULT 0,
    cert_pdf_path   TEXT
);
CREATE INDEX IF NOT EXISTS idx_dsar_status ON dsar_requests(status);
CREATE INDEX IF NOT EXISTS idx_dsar_subject ON dsar_requests(subject);

CREATE TABLE IF NOT EXISTS notifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL,         -- 'dsar_new' | 'dsar_executed' | 'system'
    title           TEXT NOT NULL,
    body            TEXT,
    target_url      TEXT,
    request_id      TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    seen            INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notif_seen ON notifications(seen);
CREATE INDEX IF NOT EXISTS idx_notif_created ON notifications(created_at);

CREATE TABLE IF NOT EXISTS entity_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical       TEXT NOT NULL,       -- canonical key (e.g. "mueller-hans")
    value           TEXT NOT NULL,       -- original observed value
    label           TEXT NOT NULL,       -- PERSON | EMPLOYEE_ID | EMAIL | PHONE
    file_id         TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    finding_id      INTEGER,
    owner           TEXT,
    co_canonical    TEXT,                -- person canonical this identifier co-occurs with
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_links_canon ON entity_links(canonical);
CREATE INDEX IF NOT EXISTS idx_links_co ON entity_links(co_canonical);
CREATE INDEX IF NOT EXISTS idx_links_file ON entity_links(file_id);

CREATE TABLE IF NOT EXISTS doc_chunks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id         TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,
    text            TEXT NOT NULL,
    vector          BLOB NOT NULL,
    dim             INTEGER NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON doc_chunks(file_id);

CREATE TABLE IF NOT EXISTS entity_embeddings (
    finding_id      INTEGER PRIMARY KEY,
    canonical       TEXT NOT NULL,
    value           TEXT NOT NULL,
    file_id         TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    vector          BLOB NOT NULL,
    dim             INTEGER NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_emb_canon ON entity_embeddings(canonical);

CREATE TABLE IF NOT EXISTS agents (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    version         TEXT NOT NULL,
    domain          TEXT NOT NULL,
    description     TEXT NOT NULL,
    tools_json      TEXT NOT NULL,
    inputs_json     TEXT NOT NULL,
    outputs_json    TEXT NOT NULL,
    endorsements    INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(path: Path | None = None) -> None:
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn(path: Path | None = None):
    path = path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
