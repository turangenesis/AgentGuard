"""FastAPI surface over the AgentGuard graph.

Endpoints:
  POST /task                    start a worker run (background), returns thread_id
  GET  /pending                 actions currently paused awaiting human approval
  POST /actions/{id}/approve    resume the paused graph -> execute the action
  POST /actions/{id}/reject     resume the paused graph -> deny the action
  GET  /feed                    recent audit-log entries
  GET  /                        health/info (the dashboard HTML is a later step)

The run model mirrors the de-risked linchpin: POST /task starts the graph as a
background task; it pauses + checkpoints at interrupt(); a *later* approve/reject
opens a fresh graph instance and resumes it by thread_id via Command(resume=...).
A background sweeper expires pending actions past their TTL (fail-safe = deny).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel

from . import db
from .cost import estimate_run_cost
from .demo import DEMO_TASK, demo_worker
from .graph import RECURSION_LIMIT, build_graph, initial_state, make_worker_model
from .mcp_server import MCP_THREAD_PREFIX
from .policy.guardian import Judge, cost_stats, default_judge

# --- configuration (env-overridable) --------------------------------------- #
AUDIT_DB = os.getenv("AGENTGUARD_DB", "agentguard.db")
CHECKPOINT_DB = os.getenv("AGENTGUARD_CHECKPOINT_DB", "agentguard_checkpoints.db")
TTL_MS = int(os.getenv("APPROVAL_TTL_MS", "120000"))
SWEEP_INTERVAL_S = float(os.getenv("AGENTGUARD_SWEEP_INTERVAL_S", "5"))

_DASHBOARD = Path(__file__).resolve().parent / "templates" / "index.html"
_CALIBRATION = Path(__file__).resolve().parent.parent / "eval" / "calibration.json"

# --- injectable factories (tests override these to use a fake worker, no key) - #
worker_factory: Callable[[], Any] = make_worker_model
judge_factory: Callable[[], Judge | None] = default_judge

# Thread ids started in demo mode, so their later resumes reuse the scripted worker
# (no API key) instead of the real LLM. In-memory: a single-process dev convenience.
_DEMO_THREADS: set[str] = set()


def make_graph(worker: Any = None):
    """Build a fresh graph instance + its own checkpointer connection.

    One per background task — matches the de-risked cross-call resume pattern and
    sidesteps cross-thread SQLite sharing. Caller must close the returned connection.
    Pass ``worker`` to override the factory (used for key-free demo runs).
    """
    conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    graph = build_graph(
        worker_model=worker if worker is not None else worker_factory(),
        judge=judge_factory(),
        checkpointer=SqliteSaver(conn),
        audit_db=AUDIT_DB,
        ttl_ms=TTL_MS,
    )
    return graph, conn


def _config(thread_id: str) -> dict:
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }


def _start_run(task: str, thread_id: str) -> None:
    graph, conn = make_graph()
    try:
        graph.invoke(initial_state(task, thread_id), _config(thread_id))
    finally:
        conn.close()


def _start_demo_run(thread_id: str) -> None:
    """Start a scripted, key-free run that hits SAFE, BLOCKED, and APPROVAL in turn."""
    graph, conn = make_graph(worker=demo_worker())
    try:
        graph.invoke(initial_state(DEMO_TASK, thread_id), _config(thread_id))
    finally:
        conn.close()


def _resume_run(thread_id: str, payload: dict) -> None:
    worker = demo_worker() if thread_id in _DEMO_THREADS else None
    graph, conn = make_graph(worker=worker)
    try:
        graph.invoke(Command(resume=payload), _config(thread_id))
    finally:
        conn.close()


async def _ttl_sweeper() -> None:
    """Expire pending actions past their TTL by resuming their graph as a denial."""
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_S)
        try:
            stale = db.stale_pending(AUDIT_DB)
        except Exception:
            continue
        for row in stale:
            payload = {"approved": False, "status": "EXPIRED"}
            await asyncio.to_thread(_resume_run, row["thread_id"], payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db(AUDIT_DB)
    sweeper = asyncio.create_task(_ttl_sweeper())
    try:
        yield
    finally:
        sweeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper


app = FastAPI(title="AgentGuard", version="0.1.0", lifespan=lifespan)


class TaskRequest(BaseModel):
    task: str


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """The live control panel — watch the feed and approve/reject paused actions."""
    return HTMLResponse(_DASHBOARD.read_text(encoding="utf-8"))


@app.get("/api")
def api_info() -> dict:
    return {
        "service": "AgentGuard",
        "tagline": "gives AI coding agents brakes",
        "dashboard": "/",
        "endpoints": [
            "/task",
            "/demo",
            "/pending",
            "/actions/{id}/approve",
            "/actions/{id}/reject",
            "/feed",
        ],
        "pending": len(db.list_pending(AUDIT_DB)),
        "judge_cost": cost_stats(),
    }


@app.post("/task")
def submit_task(req: TaskRequest, background: BackgroundTasks) -> dict:
    thread_id = uuid.uuid4().hex
    background.add_task(_start_run, req.task, thread_id)
    return {"thread_id": thread_id, "status": "started"}


@app.post("/demo")
def submit_demo(background: BackgroundTasks) -> dict:
    """Start a key-free scripted run so the dashboard is demoable without an LLM."""
    thread_id = uuid.uuid4().hex
    _DEMO_THREADS.add(thread_id)
    background.add_task(_start_demo_run, thread_id)
    return {"thread_id": thread_id, "status": "started", "mode": "demo"}


@app.get("/pending")
def get_pending() -> dict:
    return {"pending": db.list_pending(AUDIT_DB)}


@app.get("/feed")
def get_feed(limit: int = 100) -> dict:
    return {"feed": db.recent_audit(AUDIT_DB, limit=limit)}


@app.get("/calibration")
def get_calibration() -> dict:
    """Serve the saved per-action risk scores for the dashboard's calibration dial.

    Pure replay of a prior `python -m eval.calibrate` run — no API calls, no cost. The dial
    re-thresholds these client-side. Returns {available: False} if the eval hasn't been run.
    """
    if not _CALIBRATION.exists():
        return {"available": False}
    try:
        return {"available": True, **json.loads(_CALIBRATION.read_text(encoding="utf-8"))}
    except (json.JSONDecodeError, OSError):
        return {"available": False}


@app.get("/runs")
def get_runs(limit: int = 10) -> dict:
    """Recent runs with a per-run token total and a $ estimate (list-price, not billed)."""
    runs = []
    for r in db.recent_runs(AUDIT_DB, limit=limit):
        runs.append(
            {
                "thread_id": r["thread_id"],
                "task": r["task"],
                "started_at": r["started_at"],
                **estimate_run_cost(r),
            }
        )
    return {"runs": runs}


def _resolve_decision(
    action_id: str, *, approved: bool, status: str, background: BackgroundTasks
) -> dict:
    row = db.get_pending(AUDIT_DB, action_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such pending action: {action_id}")
    if row["status"] != "PENDING":
        raise HTTPException(status_code=409, detail=f"action already {row['status']}")

    if str(row["thread_id"]).startswith(MCP_THREAD_PREFIX):
        # Externally-submitted (MCP) action — there is no LangGraph run to resume. Resolve the
        # pending row directly; the external agent learns the outcome via check_review.
        db.resolve_pending(AUDIT_DB, action_id, status)
        db.append_audit(
            AUDIT_DB,
            event=status,
            thread_id=row["thread_id"],
            action_id=action_id,
            kind=row["kind"],
            target=row["target"],
            verdict="APPROVAL_REQUIRED",
            reason=row["reason"],
            detail=f"{status} via dashboard (MCP action)",
        )
    else:
        payload = {"approved": approved, "status": status}
        background.add_task(_resume_run, row["thread_id"], payload)
    return {"action_id": action_id, "status": status, "thread_id": row["thread_id"]}


@app.post("/actions/{action_id}/approve")
def approve(action_id: str, background: BackgroundTasks) -> dict:
    return _resolve_decision(action_id, approved=True, status="APPROVED", background=background)


@app.post("/actions/{action_id}/reject")
def reject(action_id: str, background: BackgroundTasks) -> dict:
    return _resolve_decision(action_id, approved=False, status="REJECTED", background=background)
