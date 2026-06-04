"""End-to-end API tests: the HTTP approve/reject path resumes a paused graph.

Uses a fake worker + no judge (no API key). Verifies the linchpin through the real
FastAPI layer: POST /task pauses at an approval; POST .../approve resumes and executes.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from agentguard import api, db
from tests._helpers import FakeWorker, ai_final, ai_tool


@pytest.fixture
def client(tmp_path, monkeypatch):
    audit_db = str(tmp_path / "audit.db")
    monkeypatch.setattr(api, "AUDIT_DB", audit_db)
    monkeypatch.setattr(api, "CHECKPOINT_DB", str(tmp_path / "ckpt.db"))
    monkeypatch.setattr(api, "SWEEP_INTERVAL_S", 3600.0)  # don't let the sweeper fire mid-test
    # One stateful fake worker shared across the start + resume background runs.
    fake = FakeWorker([ai_tool("deploy", {"target": "production"}, "c1"), ai_final("deployed")])
    monkeypatch.setattr(api, "worker_factory", lambda: fake)
    monkeypatch.setattr(api, "judge_factory", lambda: None)
    with TestClient(api.app) as c:
        c.audit_db = audit_db  # stash for assertions
        yield c


def _wait_for(fn, timeout=5.0):
    """Poll until fn() is truthy (background tasks may settle slightly after the response)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.05)
    return fn()


def test_root_reports_service(client):
    body = client.get("/").json()
    assert body["service"] == "AgentGuard"
    assert "/task" in body["endpoints"]


def test_task_pauses_and_approve_resumes_and_executes(client):
    started = client.post("/task", json={"task": "deploy to prod"})
    assert started.status_code == 200
    assert started.json()["status"] == "started"

    pending = _wait_for(lambda: client.get("/pending").json()["pending"])
    assert len(pending) == 1
    action = pending[0]
    assert action["target"] == "production"
    assert action["status"] == "PENDING"
    action_id = action["action_id"]

    approved = client.post(f"/actions/{action_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    # After resume: no longer pending, and an APPROVED event is in the feed.
    _wait_for(lambda: not client.get("/pending").json()["pending"])
    assert db.get_pending(client.audit_db, action_id)["status"] == "APPROVED"
    events = _wait_for(
        lambda: [e for e in client.get("/feed").json()["feed"] if e["event"] == "APPROVED"]
    )
    assert events


def test_reject_marks_action_rejected(client):
    client.post("/task", json={"task": "deploy to prod"})
    pending = _wait_for(lambda: client.get("/pending").json()["pending"])
    action_id = pending[0]["action_id"]

    rejected = client.post(f"/actions/{action_id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"

    _wait_for(lambda: not client.get("/pending").json()["pending"])
    assert db.get_pending(client.audit_db, action_id)["status"] == "REJECTED"


def test_approve_unknown_action_404(client):
    assert client.post("/actions/does-not-exist/approve").status_code == 404
