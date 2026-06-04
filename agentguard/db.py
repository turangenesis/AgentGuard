"""SQLite persistence: an append-only audit log + a pending-approvals work table.

Two concerns, deliberately separated:
  * ``audit``   — append-only history. Every decision/event is INSERTed, never updated.
  * ``pending`` — mutable work queue of actions awaiting a human. A row is added on
                  interrupt and its status is updated on approve/reject/expire.

A fresh connection is opened per call (cheap for SQLite, and safe across the worker
threads FastAPI uses for background runs). This is a local-first, single-user MVP.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

DEFAULT_DB = os.getenv("AGENTGUARD_DB", "agentguard.db")


@contextmanager
def _conn(db_path: str) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, and always close it."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB) -> None:
    """Create the audit + pending tables if they do not exist."""
    with _conn(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        REAL    NOT NULL,
                thread_id TEXT,
                action_id TEXT,
                kind      TEXT,
                target    TEXT,
                event     TEXT    NOT NULL,
                verdict   TEXT,
                reason    TEXT,
                rule_id   TEXT,
                source    TEXT,
                detail    TEXT
            );
            CREATE TABLE IF NOT EXISTS pending (
                action_id  TEXT PRIMARY KEY,
                thread_id  TEXT NOT NULL,
                kind       TEXT,
                target     TEXT,
                args       TEXT,
                reason     TEXT,
                rule_id    TEXT,
                source     TEXT,
                created_at REAL,
                expires_at REAL,
                status     TEXT NOT NULL DEFAULT 'PENDING'
            );
            CREATE TABLE IF NOT EXISTS run_cost (
                thread_id    TEXT PRIMARY KEY,
                task         TEXT,
                started_at   REAL,
                worker_in    INTEGER DEFAULT 0,
                worker_out   INTEGER DEFAULT 0,
                judge_in     INTEGER DEFAULT 0,
                judge_out    INTEGER DEFAULT 0,
                cache_read   INTEGER DEFAULT 0,
                cache_create INTEGER DEFAULT 0
            );
            """
        )


# --------------------------------------------------------------------------- #
# Audit log (append-only)
# --------------------------------------------------------------------------- #
def append_audit(
    db_path: str,
    *,
    event: str,
    thread_id: str | None = None,
    action_id: str | None = None,
    kind: str | None = None,
    target: str | None = None,
    verdict: str | None = None,
    reason: str | None = None,
    rule_id: str | None = None,
    source: str | None = None,
    detail: str | None = None,
) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            """INSERT INTO audit
               (ts, thread_id, action_id, kind, target, event,
                verdict, reason, rule_id, source, detail)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                time.time(),
                thread_id,
                action_id,
                kind,
                target,
                event,
                verdict,
                reason,
                rule_id,
                source,
                detail,
            ),
        )


def recent_audit(db_path: str, limit: int = 100) -> list[dict[str, Any]]:
    with _conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Pending approvals (mutable work queue)
# --------------------------------------------------------------------------- #
def add_pending(
    db_path: str,
    *,
    action_id: str,
    thread_id: str,
    kind: str,
    target: str,
    args: dict,
    reason: str,
    rule_id: str | None,
    source: str,
    ttl_ms: int,
) -> None:
    now = time.time()
    with _conn(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO pending
               (action_id, thread_id, kind, target, args, reason, rule_id, source,
                created_at, expires_at, status)
               VALUES (?,?,?,?,?,?,?,?,?,?, 'PENDING')""",
            (
                action_id,
                thread_id,
                kind,
                target,
                json.dumps(args, default=str),
                reason,
                rule_id,
                source,
                now,
                now + ttl_ms / 1000.0,
            ),
        )


def get_pending(db_path: str, action_id: str) -> dict[str, Any] | None:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM pending WHERE action_id = ?", (action_id,)).fetchone()
    return dict(row) if row else None


def list_pending(db_path: str) -> list[dict[str, Any]]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM pending WHERE status = 'PENDING' ORDER BY created_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def resolve_pending(db_path: str, action_id: str, status: str) -> None:
    """Mark a pending action APPROVED / REJECTED / EXPIRED (no longer PENDING)."""
    with _conn(db_path) as conn:
        conn.execute("UPDATE pending SET status = ? WHERE action_id = ?", (status, action_id))


# --------------------------------------------------------------------------- #
# Per-run token accounting (for the dashboard cost line)
# --------------------------------------------------------------------------- #
def add_run_cost(
    db_path: str,
    thread_id: str,
    *,
    task: str | None = None,
    worker_in: int = 0,
    worker_out: int = 0,
    judge_in: int = 0,
    judge_out: int = 0,
    cache_read: int = 0,
    cache_create: int = 0,
) -> None:
    """Accumulate token usage for one run. First write sets task/started_at; the
    rest add up. Zero-token calls (fake/demo workers) still create the row."""
    now = time.time()
    with _conn(db_path) as conn:
        conn.execute(
            """INSERT INTO run_cost
                 (thread_id, task, started_at, worker_in, worker_out,
                  judge_in, judge_out, cache_read, cache_create)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(thread_id) DO UPDATE SET
                 worker_in    = worker_in    + excluded.worker_in,
                 worker_out   = worker_out   + excluded.worker_out,
                 judge_in     = judge_in     + excluded.judge_in,
                 judge_out    = judge_out    + excluded.judge_out,
                 cache_read   = cache_read   + excluded.cache_read,
                 cache_create = cache_create + excluded.cache_create,
                 task         = COALESCE(run_cost.task, excluded.task)""",
            (
                thread_id,
                task,
                now,
                worker_in,
                worker_out,
                judge_in,
                judge_out,
                cache_read,
                cache_create,
            ),
        )


def recent_runs(db_path: str, limit: int = 10) -> list[dict[str, Any]]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM run_cost ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def stale_pending(db_path: str, now: float | None = None) -> list[dict[str, Any]]:
    """Return PENDING actions whose TTL has elapsed (for the expiry sweeper)."""
    now = time.time() if now is None else now
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM pending WHERE status = 'PENDING' AND expires_at <= ?", (now,)
        ).fetchall()
    return [dict(r) for r in rows]
