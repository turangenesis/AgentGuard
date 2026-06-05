"""MCP server tests — the review/poll core logic (key-free; rules + fail-safe, no API key)."""

from __future__ import annotations

import pytest

from agentguard import db, mcp_server


@pytest.fixture
def mcp_db(tmp_path, monkeypatch):
    path = str(tmp_path / "mcp.db")
    monkeypatch.setattr(mcp_server, "AUDIT_DB", path)
    return path


def test_safe_action_is_allowed(mcp_db):
    r = mcp_server.review_action("read", "read_file", "src/index.ts", judge=None)
    assert r["status"] == "allow"
    assert r["verdict"] == "SAFE"


def test_destructive_action_is_blocked(mcp_db):
    r = mcp_server.review_action("shell", "run_shell", "rm -rf /", judge=None)
    assert r["status"] == "blocked"
    assert r["verdict"] == "BLOCKED"


def test_deploy_is_pending_then_pollable(mcp_db):
    r = mcp_server.review_action("deploy", "deploy", "production", judge=None)
    assert r["status"] == "pending"
    action_id = r["action_id"]

    # The external agent polls — it's pending until a human decides.
    assert mcp_server.get_review(action_id)["status"] == "pending"
    assert db.get_pending(mcp_db, action_id) is not None  # visible to the dashboard too

    # A human approves (what the dashboard's approve endpoint does for an MCP action).
    db.resolve_pending(mcp_db, action_id, "APPROVED")
    assert mcp_server.get_review(action_id)["status"] == "approved"


def test_no_rule_action_fails_safe_to_pending(mcp_db):
    # No rule matches and no judge -> fail-safe APPROVAL_REQUIRED (never silently allowed).
    r = mcp_server.review_action("shell", "run_shell", "npm install lodash", judge=None)
    assert r["status"] == "pending"


def test_unknown_action_id(mcp_db):
    assert mcp_server.get_review("does-not-exist")["status"] == "unknown"
