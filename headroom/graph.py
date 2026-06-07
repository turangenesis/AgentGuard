"""The LangGraph runtime: worker -> guardian -> (execute | interrupt | deny) -> loop.

This is the heart of Headroom. A real worker LLM proposes
one tool call at a time; the guardian classifies it; SAFE executes, BLOCKED is denied,
and APPROVAL_REQUIRED hits an ``interrupt()`` node that pauses the graph and checkpoints
state to SQLite. A later ``Command(resume=...)`` (from the API, by ``thread_id``)
continues the run. Every decision is appended to the audit log.

The worker model and the guardian judge are both injected, so the entire graph is
testable with a fake worker and no API key (see tests/test_graph.py).
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from . import db
from .policy.guardian import Judge, classify, cost_stats
from .tools import TOOLS_BY_NAME, action_from_tool_call
from .types import ActionKind, ProposedAction

MAX_STEPS = 12  # worker turns before we force-stop (belt-and-suspenders vs. loops)
RECURSION_LIMIT = 60

WORKER_SYSTEM = """\
You are an autonomous coding agent working on the repository at the current root.
Accomplish the user's task by calling tools.

Rules of engagement:
- Propose exactly ONE tool call at a time, then wait for its result.
- File paths are relative to the repo root (e.g. "src/index.ts").
- Some actions may be blocked or require human approval; you will get a tool result
  telling you so. If an action is denied, adapt or explain — do not retry it blindly.
- When the task is complete, reply with a short plain-text summary and NO tool call.

Available tools: read_file, list_dir, write_file, run_shell, git, create_pr, deploy.
"""


class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    task: str
    thread_id: str
    current: dict | None  # the action currently being classified/executed
    decision: dict | None  # the guardian's verdict on `current`
    review: dict | None  # the human decision delivered via Command(resume=...)
    steps: int


def make_worker_model(model: str = "claude-sonnet-4-6") -> Any:
    """Build the real worker LLM with tools bound. Requires ANTHROPIC_API_KEY.

    Parallel tool calls are disabled so the worker proposes one action at a time —
    exactly one trip through the guardian gate per turn.
    """
    from langchain_anthropic import ChatAnthropic

    from .tools import TOOLS

    llm = ChatAnthropic(model=model, temperature=0, max_tokens=1024)
    return llm.bind_tools(TOOLS, parallel_tool_calls=False)


def initial_state(task: str, thread_id: str) -> GraphState:
    return {
        "messages": [SystemMessage(content=WORKER_SYSTEM), HumanMessage(content=task)],
        "task": task,
        "thread_id": thread_id,
        "current": None,
        "decision": None,
        "review": None,
        "steps": 0,
    }


def _action_to_dict(a: ProposedAction) -> dict:
    return {
        "id": a.id,
        "kind": a.kind.value,
        "tool": a.tool,
        "args": a.args,
        "target": a.target,
        "tool_call_id": a.tool_call_id,
    }


def _dict_to_action(d: dict) -> ProposedAction:
    return ProposedAction(
        id=d["id"],
        kind=ActionKind(d["kind"]),
        tool=d["tool"],
        args=d.get("args", {}),
        target=d.get("target", ""),
        tool_call_id=d.get("tool_call_id"),
    )


def build_graph(
    worker_model: Any,
    judge: Judge | None = None,
    checkpointer: Any = None,
    audit_db: str = db.DEFAULT_DB,
    ttl_ms: int = 120_000,
):
    """Compile the Headroom graph. ``worker_model`` needs a ``.invoke(messages)`` ->
    AIMessage interface (real: ChatAnthropic.bind_tools(...); tests: a fake)."""

    # ----- nodes ----------------------------------------------------------- #
    def worker(state: GraphState) -> dict:
        steps = state.get("steps", 0) + 1
        thread_id = state["thread_id"]
        if steps == 1:
            # Open the run on the activity feed and create its cost row.
            db.append_audit(
                audit_db,
                event="TASK_STARTED",
                thread_id=thread_id,
                detail=str(state.get("task", ""))[:500],
            )
            db.add_run_cost(audit_db, thread_id, task=state.get("task"))
        if steps > MAX_STEPS:
            return {
                "messages": [AIMessage(content="[step limit reached — stopping]")],
                "current": None,
                "steps": steps,
            }
        ai = worker_model.invoke(state["messages"])
        # Per-run cost: record the worker's token usage (no-op for fake/demo workers).
        usage = getattr(ai, "usage_metadata", None) or {}
        if usage:
            db.add_run_cost(
                audit_db,
                thread_id,
                worker_in=usage.get("input_tokens", 0) or 0,
                worker_out=usage.get("output_tokens", 0) or 0,
            )
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            # The worker finished with a plain-text reply (e.g. an off-topic ask) —
            # surface it on the activity feed instead of a blank screen.
            text = ai.content if isinstance(ai.content, str) else str(ai.content)
            db.append_audit(
                audit_db,
                event="AGENT_REPLY",
                thread_id=thread_id,
                reason="Agent responded with no action.",
                detail=text[:500],
            )
            return {"messages": [ai], "current": None, "steps": steps}

        action = action_from_tool_call(tool_calls[0])
        msgs: list = [ai]
        # We gate one action at a time; immediately answer any extra tool calls so the
        # message protocol stays valid (every tool_use needs a tool_result).
        for tc in tool_calls[1:]:
            msgs.append(
                ToolMessage(
                    content=(
                        "Deferred: Headroom reviews one action at a time. Resubmit this next."
                    ),
                    tool_call_id=tc["id"],
                )
            )
        return {"messages": msgs, "current": _action_to_dict(action), "steps": steps}

    def guardian(state: GraphState) -> dict:
        cur = state["current"]
        action = _dict_to_action(cur)
        # Attribute any LLM-judge tokens spent on THIS action to the run, via the
        # delta of the global judge meter. (Single-process/local: runs are sequential.)
        before = cost_stats()
        decision = classify(action, judge)
        after = cost_stats()
        d_in = after["input_tokens"] - before["input_tokens"]
        d_out = after["output_tokens"] - before["output_tokens"]
        d_cr = after["cache_read_tokens"] - before["cache_read_tokens"]
        d_cc = after["cache_creation_tokens"] - before["cache_creation_tokens"]
        if d_in or d_out or d_cr or d_cc:
            db.add_run_cost(
                audit_db,
                state["thread_id"],
                judge_in=d_in,
                judge_out=d_out,
                cache_read=d_cr,
                cache_create=d_cc,
            )
        dec = {
            "verdict": decision.verdict.value,
            "reason": decision.reason,
            "rule_id": decision.rule_id,
            "source": decision.source.value,
        }
        db.append_audit(
            audit_db,
            event="PROPOSED",
            thread_id=state["thread_id"],
            action_id=cur["id"],
            kind=cur["kind"],
            target=cur["target"],
            verdict=dec["verdict"],
            reason=dec["reason"],
            rule_id=dec["rule_id"],
            source=dec["source"],
        )
        if decision.verdict.value == "APPROVAL_REQUIRED":
            db.add_pending(
                audit_db,
                action_id=cur["id"],
                thread_id=state["thread_id"],
                kind=cur["kind"],
                target=cur["target"],
                args=cur["args"],
                reason=dec["reason"],
                rule_id=dec["rule_id"],
                source=dec["source"],
                ttl_ms=ttl_ms,
            )
        return {"decision": dec}

    def human_review(state: GraphState) -> dict:
        # NOTE: no side effects before interrupt() — this node re-executes on resume.
        cur = state["current"]
        dec = state["decision"]
        review = interrupt(
            {
                "action_id": cur["id"],
                "thread_id": state["thread_id"],
                "kind": cur["kind"],
                "tool": cur["tool"],
                "target": cur["target"],
                "verdict": dec["verdict"],
                "reason": dec["reason"],
            }
        )
        if not isinstance(review, dict):
            review = {
                "approved": bool(review),
                "status": "APPROVED" if review else "REJECTED",
            }
        return {"review": review}

    def execute(state: GraphState) -> dict:
        cur = state["current"]
        dec = state["decision"]
        tool = TOOLS_BY_NAME.get(cur["tool"])
        try:
            result = tool.invoke(cur["args"]) if tool else f"ERROR: unknown tool {cur['tool']}"
        except Exception as exc:  # noqa: BLE001 — surface tool errors to the worker
            result = f"ERROR: {exc}"

        if dec["verdict"] == "APPROVAL_REQUIRED":
            status = (state.get("review") or {}).get("status", "APPROVED")
            db.resolve_pending(audit_db, cur["id"], status)
            event = "APPROVED"
        else:
            event = "EXECUTED"
        db.append_audit(
            audit_db,
            event=event,
            thread_id=state["thread_id"],
            action_id=cur["id"],
            kind=cur["kind"],
            target=cur["target"],
            verdict=dec["verdict"],
            reason=dec["reason"],
            detail=str(result)[:500],
        )
        msg = ToolMessage(content=str(result), tool_call_id=cur["tool_call_id"] or cur["id"])
        return {"messages": [msg], "current": None, "decision": None, "review": None}

    def deny(state: GraphState) -> dict:
        cur = state["current"]
        dec = state["decision"]
        review = state.get("review") or {}
        if dec["verdict"] == "BLOCKED":
            status = "BLOCKED"
        else:  # APPROVAL_REQUIRED that the human rejected, or that expired
            status = review.get("status", "REJECTED")
            db.resolve_pending(audit_db, cur["id"], status)
        db.append_audit(
            audit_db,
            event=status,
            thread_id=state["thread_id"],
            action_id=cur["id"],
            kind=cur["kind"],
            target=cur["target"],
            verdict=dec["verdict"],
            reason=dec["reason"],
            detail=f"{status}: action not executed.",
        )
        msg = ToolMessage(
            content=f"DENIED ({status}): {dec['reason']} This action was not executed.",
            tool_call_id=cur["tool_call_id"] or cur["id"],
        )
        return {"messages": [msg], "current": None, "decision": None, "review": None}

    # ----- routing --------------------------------------------------------- #
    def route_after_worker(state: GraphState) -> str:
        return "guardian" if state.get("current") else END

    def route_after_guardian(state: GraphState) -> str:
        verdict = state["decision"]["verdict"]
        if verdict == "SAFE":
            return "execute"
        if verdict == "BLOCKED":
            return "deny"
        return "human_review"

    def route_after_review(state: GraphState) -> str:
        return "execute" if (state.get("review") or {}).get("approved") else "deny"

    # ----- wire it up ------------------------------------------------------ #
    builder = StateGraph(GraphState)
    builder.add_node("worker", worker)
    builder.add_node("guardian", guardian)
    builder.add_node("human_review", human_review)
    builder.add_node("execute", execute)
    builder.add_node("deny", deny)

    builder.add_edge(START, "worker")
    builder.add_conditional_edges("worker", route_after_worker, ["guardian", END])
    builder.add_conditional_edges(
        "guardian", route_after_guardian, ["execute", "deny", "human_review"]
    )
    builder.add_conditional_edges("human_review", route_after_review, ["execute", "deny"])
    builder.add_edge("execute", "worker")
    builder.add_edge("deny", "worker")

    return builder.compile(checkpointer=checkpointer)


def is_paused(result: dict) -> bool:
    """True if a graph invoke/resume returned because it hit an interrupt."""
    return isinstance(result, dict) and "__interrupt__" in result
