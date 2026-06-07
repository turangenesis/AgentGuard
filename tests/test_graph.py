"""Integration tests for the LangGraph runtime, driven by a fake worker (no API key).

Covers: BLOCKED denies inline; APPROVAL_REQUIRED pauses at interrupt(); resume
APPROVED -> execute; resume REJECTED / EXPIRED -> deny; and that real reads return
actual sample-target/ content.
"""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from headroom import db
from headroom.graph import build_graph, initial_state, is_paused
from tests._helpers import FakeWorker, ai_final, ai_tool


def _make(fake, audit_db, ckpt_path):
    conn = sqlite3.connect(ckpt_path, check_same_thread=False)
    graph = build_graph(
        worker_model=fake, judge=None, checkpointer=SqliteSaver(conn), audit_db=audit_db
    )
    return graph, conn


def _cfg(thread_id):
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}


def _setup(tmp_path):
    audit_db = str(tmp_path / "audit.db")
    ckpt = str(tmp_path / "ckpt.db")
    db.init_db(audit_db)
    return audit_db, ckpt


def _events(audit_db):
    return [r["event"] for r in db.recent_audit(audit_db)]


def test_blocked_action_denied_without_pausing(tmp_path):
    audit_db, ckpt = _setup(tmp_path)
    fake = FakeWorker(
        [ai_tool("read_file", {"path": "sample-target/.env"}, "c1"), ai_final("stopped")]
    )
    graph, conn = _make(fake, audit_db, ckpt)
    try:
        result = graph.invoke(initial_state("read the env file", "tA"), _cfg("tA"))
    finally:
        conn.close()

    assert not is_paused(result)
    assert "BLOCKED" in _events(audit_db)
    assert db.list_pending(audit_db) == []  # blocked never becomes a pending approval


def test_approval_pauses_then_resume_approved_executes(tmp_path):
    audit_db, ckpt = _setup(tmp_path)
    fake = FakeWorker([ai_tool("deploy", {"target": "production"}, "c1"), ai_final("deployed")])

    graph1, conn1 = _make(fake, audit_db, ckpt)
    try:
        r1 = graph1.invoke(initial_state("deploy to prod", "tB"), _cfg("tB"))
    finally:
        conn1.close()
    assert is_paused(r1)
    pending = db.list_pending(audit_db)
    assert len(pending) == 1
    action_id = pending[0]["action_id"]

    # Fresh graph instance + connection (mirrors the API resuming a later HTTP call).
    graph2, conn2 = _make(fake, audit_db, ckpt)
    try:
        r2 = graph2.invoke(Command(resume={"approved": True, "status": "APPROVED"}), _cfg("tB"))
    finally:
        conn2.close()

    assert not is_paused(r2)
    assert db.get_pending(audit_db, action_id)["status"] == "APPROVED"
    assert "APPROVED" in _events(audit_db)


def test_approval_resume_rejected_denies(tmp_path):
    audit_db, ckpt = _setup(tmp_path)
    fake = FakeWorker([ai_tool("deploy", {"target": "production"}, "c1"), ai_final("aborted")])

    graph1, conn1 = _make(fake, audit_db, ckpt)
    try:
        r1 = graph1.invoke(initial_state("deploy to prod", "tC"), _cfg("tC"))
    finally:
        conn1.close()
    assert is_paused(r1)
    action_id = db.list_pending(audit_db)[0]["action_id"]

    graph2, conn2 = _make(fake, audit_db, ckpt)
    try:
        graph2.invoke(Command(resume={"approved": False, "status": "REJECTED"}), _cfg("tC"))
    finally:
        conn2.close()

    assert db.get_pending(audit_db, action_id)["status"] == "REJECTED"
    assert "REJECTED" in _events(audit_db)


def test_ttl_expiry_resume_denies(tmp_path):
    audit_db, ckpt = _setup(tmp_path)
    fake = FakeWorker([ai_tool("deploy", {"target": "production"}, "c1"), ai_final("expired")])

    graph1, conn1 = _make(fake, audit_db, ckpt)
    try:
        graph1.invoke(initial_state("deploy to prod", "tD"), _cfg("tD"))
    finally:
        conn1.close()
    action_id = db.list_pending(audit_db)[0]["action_id"]

    # The sweeper resumes a stale pending as EXPIRED -> deny.
    graph2, conn2 = _make(fake, audit_db, ckpt)
    try:
        graph2.invoke(Command(resume={"approved": False, "status": "EXPIRED"}), _cfg("tD"))
    finally:
        conn2.close()

    assert db.get_pending(audit_db, action_id)["status"] == "EXPIRED"
    assert "EXPIRED" in _events(audit_db)


def test_safe_actions_execute_and_reads_are_real(tmp_path):
    audit_db, ckpt = _setup(tmp_path)
    fake = FakeWorker(
        [
            ai_tool("read_file", {"path": "src/index.ts"}, "c1"),
            ai_tool("write_file", {"path": "docs/notes.md", "content": "hi"}, "c2"),
            ai_final("done"),
        ]
    )
    graph, conn = _make(fake, audit_db, ckpt)
    try:
        result = graph.invoke(initial_state("read then document", "tE"), _cfg("tE"))
    finally:
        conn.close()

    assert not is_paused(result)
    audit = db.recent_audit(audit_db)
    executed = [r for r in audit if r["event"] == "EXECUTED"]
    assert len(executed) == 2  # the real read + the simulated doc write
    # The real read returned actual sample-target/src/index.ts content.
    read_row = next(r for r in audit if r["kind"] == "read")
    assert "taskflow-api" in (read_row["detail"] or "")
