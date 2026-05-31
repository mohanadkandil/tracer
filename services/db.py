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
