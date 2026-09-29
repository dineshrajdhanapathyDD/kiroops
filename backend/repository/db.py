"""SQLite connection factory and schema bootstrap.

This is the only module that opens raw SQLite connections. It applies the
schema DDL for the four tables defined in ``design.md`` (incidents,
timeline_events, diagnoses, remediation_actions), enables foreign-key
enforcement, and supports an in-memory database for tests.
"""

from __future__ import annotations

import sqlite3

from backend.config import IN_MEMORY_DB_PATH, get_db_path

# Schema DDL matching design.md exactly. Statements are idempotent
# (IF NOT EXISTS) so bootstrap can run against an existing database safely.
SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS incidents (
    num          INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id  TEXT NOT NULL UNIQUE,
    title        TEXT NOT NULL,
    severity     TEXT NOT NULL,
    service      TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS timeline_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id  TEXT NOT NULL REFERENCES incidents(incident_id),
    seq          INTEGER NOT NULL,
    type         TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    details      TEXT NOT NULL,
    UNIQUE (incident_id, seq)
);

CREATE TABLE IF NOT EXISTS diagnoses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id   TEXT NOT NULL REFERENCES incidents(incident_id),
    summary       TEXT NOT NULL,
    evidence_refs TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS remediation_actions (
    action_id    TEXT PRIMARY KEY,
    incident_id  TEXT NOT NULL REFERENCES incidents(incident_id),
    description  TEXT NOT NULL,
    rationale    TEXT NOT NULL
);
"""

# The four table names the schema defines, in creation order.
TABLE_NAMES: tuple[str, ...] = (
    "incidents",
    "timeline_events",
    "diagnoses",
    "remediation_actions",
)


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with project conventions applied.

    - ``db_path`` defaults to the configured path (see ``config.get_db_path``).
    - Pass ``":memory:"`` (``config.IN_MEMORY_DB_PATH``) for a transient
      in-memory database, used by tests.
    - Foreign-key enforcement is enabled (``PRAGMA foreign_keys=ON``); SQLite
      requires this per-connection.
    - Rows are returned as ``sqlite3.Row`` for name-based access.
    - ``check_same_thread=False`` so the connection can be used from FastAPI's
      threadpool (sync endpoints run in worker threads). The service layer owns
      transactions and callers use a single connection, so cross-thread use is
      safe here.
    """
    path = get_db_path() if db_path is None else db_path
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    """Apply the schema DDL, creating any missing tables."""
    conn.executescript(SCHEMA_DDL)
    conn.commit()


def bootstrap(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection and ensure the schema exists.

    Returns a ready-to-use connection. The caller owns closing it.
    """
    conn = connect(db_path)
    apply_schema(conn)
    return conn


def in_memory() -> sqlite3.Connection:
    """Open a bootstrapped in-memory database (for tests)."""
    return bootstrap(IN_MEMORY_DB_PATH)
