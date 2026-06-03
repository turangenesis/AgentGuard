# AgentGuard

**Human-in-the-loop execution firewall for AI coding agents.**
*OpenClaw gives agents hands. AgentGuard gives them brakes.*

A **worker LLM agent** proposes actions (file, shell, git, deploy). A **guardian agent** — deterministic rules backed by LLM risk judgment — classifies each as **safe / approval-required / blocked**. Risky actions pause the agent mid-task (LangGraph `interrupt()`) and wait for a human to approve or reject. Every decision is written to an append-only audit log and shown on a live dashboard.

> **Status:** initial setup — implementation in progress. See the [roadmap](ROADMAP.md).

## Why

As teams run AI coding agents across repos, they need a layer that **judges, gates, and logs** agent actions before they touch secrets, the `main` branch, or production. AgentGuard is that layer — and a demonstration of **multi-agent orchestration** (a guardian agent supervising a worker agent) with a **human in the loop**.

## How it works

```
worker agent → proposes action → guardian (rules → LLM) ─┬─ SAFE     ▸ run
                                                         ├─ BLOCKED  ▸ deny
                                                         └─ APPROVAL ▸ pause (interrupt)
                                                                       → human approve / reject
                                                                       → resume / abort
                                          → append-only audit log + live dashboard
```

## Roadmap

The MVP is the foundation; each stage above it hardens or extends the control plane:

- **Stage 1 — Adversarial robustness** *(next)* — red-team the guardian against prompt injection; measure attack-hold rate vs. a baseline.
- **Stage 2 — Real sandboxed execution** — stop a *real* `rm -rf`, not a simulated one.
- **Stage 3 — Fleet control tower**, plus **remote approval** — approve / reject from your phone.

Full detail → **[ROADMAP.md](ROADMAP.md)**.

## Getting Started

```bash
pip install -r requirements.txt        # or: uv sync
cp .env.example .env                    # add ANTHROPIC_API_KEY (and optional LangSmith key)
```

## Usage

```bash
uvicorn agentguard.api:app --reload     # dashboard → http://localhost:8000
python -m scripts.demo                  # demo: worker proposes, guardian gates, you approve
```

Tests use a fake worker and need **no** API key. Real runs and the eval require `ANTHROPIC_API_KEY`.

## Development

```bash
pytest                                  # unit + integration
python -m eval.run_eval                 # guardian confusion matrix + recall / precision
bash scripts/smoke-check.sh             # scaffolding checks (+ pytest once implemented)
```

## Stack

Python 3.12 · LangGraph (`interrupt()` HITL + SqliteSaver) · langchain-anthropic (Claude) · FastAPI · SQLite · MCP (FastMCP) · LangSmith · Tailwind-CDN dashboard.

## License

MIT — see [LICENSE](LICENSE).
