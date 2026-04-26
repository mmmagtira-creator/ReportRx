"""SQLite persistence layer for ReportRx."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Dict, Generator, List, Optional

from app.config import DB_PATH

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS reports (
    case_id       TEXT PRIMARY KEY,
    text_report   TEXT NOT NULL,
    drug_mention  TEXT NOT NULL DEFAULT '',
    reaction_mention TEXT NOT NULL DEFAULT '',
    onset         TEXT NOT NULL DEFAULT '',
    raw_confidence REAL NOT NULL DEFAULT 0.0,
    status        TEXT NOT NULL DEFAULT '',
    latency_ms    REAL NOT NULL DEFAULT 0.0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_COUNTER = """
CREATE TABLE IF NOT EXISTS counters (
    name  TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);
"""


def init_db() -> None:
    """Create tables if they don't exist yet."""
    with _connect() as conn:
        conn.executescript(_CREATE_TABLE + _CREATE_COUNTER)
        # Seed the counter if missing
        conn.execute(
            "INSERT OR IGNORE INTO counters (name, value) VALUES ('case_seq', 0)"
        )


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def next_case_id() -> str:
    """Atomically increment and return the next case ID."""
    with _connect() as conn:
        conn.execute(
            "UPDATE counters SET value = value + 1 WHERE name = 'case_seq'"
        )
        row = conn.execute(
            "SELECT value FROM counters WHERE name = 'case_seq'"
        ).fetchone()
        seq = row["value"]
    return f"case_{seq:05d}"


def insert_report(report: Dict) -> None:
    """Persist a single analyzed report row."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO reports
                (case_id, text_report, drug_mention, reaction_mention,
                 onset, raw_confidence, status, latency_ms)
            VALUES
                (:case_id, :text_report, :drug_mention, :reaction_mention,
                 :onset, :raw_confidence, :status, :latency_ms)
            """,
            report,
        )


def get_reports(status: Optional[str] = None) -> List[Dict]:
    """Return reports in insertion order, optionally filtered by status."""
    with _connect() as conn:
        query = """
            SELECT case_id, text_report, drug_mention, reaction_mention,
                   onset, raw_confidence, status, latency_ms
            FROM reports
        """
        params: tuple = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY rowid ASC"
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_all_reports() -> List[Dict]:
    """Return all reports in insertion order."""
    return get_reports()


def get_report_count() -> int:
    """Return total number of persisted reports."""
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM reports").fetchone()
    return row["cnt"]


def clear_all_reports() -> None:
    """Delete all reports and reset the case ID counter to 0."""
    with _connect() as conn:
        conn.execute("DELETE FROM reports")
        conn.execute("UPDATE counters SET value = 0 WHERE name = 'case_seq'")

