# ARCHITECTURE.md

System architecture reference. Update when structure changes meaningfully.

---

## What This Is

Headroom is a human-in-the-loop execution firewall for AI coding agents. A **worker LLM agent** proposes tool calls; a **guardian agent** (deterministic rules + LLM risk judgment) classifies each as *safe / approval-required / blocked*; risky actions **pause the LangGraph run via `interrupt()`** and wait for human approval; every decision is written to an **append-only audit log** and shown on a live dashboard.

## Stack

- **Language:** Python 3.12
- **Orchestration:** LangGraph — state graph + `interrupt()` HITL + `SqliteSaver` checkpointer
- **LLM:** Anthropic Claude via `langchain-anthropic` (one client for worker + guardian; prompt caching on the guardian)
- **API / server:** FastAPI (+ uvicorn)
- **Database:** SQLite (LangGraph checkpointer state + an append-only audit table)
- **Integration:** MCP server via FastMCP (`submit_action_for_review`, `check_review`)
- **Observability:** LangSmith tracing + audit log + dashboard
- **Dashboard:** single HTML page, Tailwind via CDN, 1s polling (no build step)
- **Deployment target:** Local-first, single user (hosted/multi-user is future work)

## Directory Structure

```
headroom/
  types.py             # ProposedAction, Verdict, ActionKind (Pydantic)
  policy/
    rules.py           # ordered deterministic ruleset (policy-as-data)
    guardian.py        # classify(): rules first-match → else one LLM judge call
  tools.py             # worker tools: read/list REAL (sample-target/); write/shell/git/deploy SIMULATED
  graph.py             # LangGraph: worker → guardian → interrupt() on APPROVAL; SqliteSaver
  db.py                # SQLite connection + append-only audit table
  api.py               # FastAPI: /task /pending /actions/{id}/approve|reject /feed
  mcp_server.py        # MCP server (FastMCP) wrapping the guardian + approval path
  templates/index.html # minimal dashboard (Tailwind CDN, 1s poll)
sample-target/         # bundled repo with tripwires (.env, src/auth/, deploy.sh) — reads are real
scripts/demo.py        # curated + scripted-fallback demo run
eval/                  # dataset.jsonl + run_eval.py (confusion matrix, recall/precision)
tests/                 # test_guardian.py, test_graph.py (fake worker → no API key needed)
```

## Core Data Flow

`POST /task` → LangGraph graph (background task, `SqliteSaver`) → worker proposes a tool call → guardian classifies (rules → else LLM) → **SAFE** executes / **BLOCKED** denied / **APPROVAL_REQUIRED** pauses via `interrupt()` (state checkpointed) → human approves|rejects on the dashboard → API resumes the graph by `thread_id` via `Command(resume=…)` → execute (or simulate) → loop. Every step is appended to the audit log.

**Fail-safe defaults:** unmatched action → APPROVAL_REQUIRED; pending past TTL (~120s) → EXPIRED = deny.

## Key Constraints

- Local-first, single-user MVP.
- Requires `ANTHROPIC_API_KEY` for real worker/guardian runs and the eval; tests use a fake worker and need no key.
- Dangerous tools (write/shell/git/deploy) are **simulated**; only reads touch the real `sample-target/`.
- The cross-call `interrupt()` → `Command(resume=…)` by `thread_id` is the linchpin (background task + correct checkpoint threading).
- The LangGraph interrupt/resume and MCP SDK surfaces are evolving; the implementation tracks current published APIs for compatibility.
- Ruleset ~10–12 rules; per-repo policy config is deferred.
