# AgentGuard

**A calibrated execution firewall for AI coding agents.**
*OpenClaw gives agents hands. AgentGuard gives them brakes.*

> **The thesis:** Stopping an agent is a *framework feature* — a brake pedal. Knowing **when** to stop it, and being able to **measure and tune** that judgment, is the product. A pause button is plumbing (LangGraph hands it to you for free); what it *can't* tell you is whether your approval policy is too paranoid (humans rubber-stamp every alert until the gate is useless) or too lax (something blows up). AgentGuard makes that judgment **measurable and tunable**.
>
> *Anyone can stop an agent. AgentGuard knows when to — and proves it.*

A **worker LLM agent** proposes actions (file, shell, git, deploy). A **guardian** — deterministic rules backed by an LLM risk judgment — classifies each as **safe / approval-required / blocked**. Risky actions pause the agent mid-task (LangGraph `interrupt()`) and wait for a human. Every decision is audit-logged and shown on a live dashboard. And the guardian's judgment is **evaluated as a calibration problem** — *selective classification under asymmetric cost with noisy labels* — so its risk tolerance is a measured dial, not a vibe.

> **Status:** MVP built — worker + guardian + HITL gate + audit + live dashboard + a **calibration eval**. Stage 1 (calibration depth + adversarial robustness) is next. See the **[roadmap](ROADMAP.md)**.

## The problem (why this isn't "just a pause button")

As agents get real hands — deploy, delete, spend money, touch prod — the bottleneck isn't *can* we stop them; frameworks already do that. The bottleneck is *can we trust the thing deciding when to stop them.* Over-gate and humans rubber-stamp every alert until the guard is useless; under-gate and something blows up. Today that line is usually set by vibes. AgentGuard sets it **with data**.

## How it works

```
worker agent → proposes action → guardian (rules → LLM) ─┬─ SAFE     ▸ run
                                                         ├─ BLOCKED  ▸ deny
                                                         └─ APPROVAL ▸ pause (interrupt)
                                                                       → human approve / reject
                                                                       → resume / abort
                                          → append-only audit log + live dashboard
```

The gate is the **substrate**. The **moat** is the layer above it: measuring whether the gate's judgment is any good.

## The calibration eval (the moat)

The guardian emits a **0–100 risk score** per action. Sweeping the auto-allow-vs-escalate threshold produces the **safety/utility tradeoff curve** — missed-danger rate vs false-alarm rate — under an **asymmetric cost matrix** (auto-allowing danger is catastrophic; a false alarm is annoyance).

```bash
python -m eval.calibrate            # prints the sweep + cost-min & Neyman-Pearson points + AURC
python -m eval.calibrate --plot     # also writes eval/calibration.png
```

![AgentGuard calibration curve — safety/utility tradeoff and expected cost vs threshold](eval/calibration.png)

On the current **30-row hand-labeled set** (small, reported as such — not a published benchmark), the LLM-scored guardian hits a sweet spot at **0% dangerous-miss with ~10% false-alarm**, and the curve shows exactly what each click of "more permissive" costs in missed danger. That's the artifact: *pick your risk tolerance with data, not vibes.*

**The noise floor — why a single "ground truth" is a lie.** "Is this action risky?" is *subjective*: even careful reviewers disagree, so a guard can't be scored against one objective label. `python -m eval.noise_floor` has three LLM-persona reviewers (cautious / pragmatic / strict-compliance) label the set and reports **Fleiss' κ ≈ 0.53** — only *moderate* agreement. That's the *irreducible* disagreement, and it's the honest yardstick: a guard that agrees with reviewers as often as they agree with each other is at "human" level. *(Personas are a **proxy** for human annotators — reported as such, not the true human floor.)*

> **Precision note (so the claim is exact):** the curve is **operating-point analysis under asymmetric cost** (selective classification) — *not yet formal calibration* in the ECE/reliability sense. "Calibration" is the theme; the claim is precisely the measured tradeoff + noise floor above. Formal calibration metrics (ECE, Brier, reliability diagrams), an adversarial/evasion set, published benchmarks (AgentDojo, InjecAgent), and frontier methods (conformal prediction, trajectory-level guarding) are deeper rigor on the roadmap — see **[Stage 1](ROADMAP.md)**.

> **The throughline:** *Stopping an agent is a framework feature. Knowing when to stop it — selective classification under asymmetric cost with label noise — is the problem, and here's the curve that shows the tradeoff and lets me set the operating point with data.*

## Getting Started

```bash
pip install -r requirements.txt        # or: uv sync
cp .env.example .env                    # add ANTHROPIC_API_KEY (and optional LangSmith key)
```

## Usage

```bash
uvicorn agentguard.api:app              # dashboard → http://localhost:8000 (Run demo needs no key)
```

The dashboard shows a live activity feed, pending approvals with the guardian's reasoning, approve/reject, and a per-run cost line. The **Run demo** button drives a full SAFE → BLOCKED → APPROVAL flow with **no API key**.

## Development

```bash
pytest                                  # unit + integration (no API key needed)
python -m eval.run_eval                 # guardian confusion matrix + recall / precision
python -m eval.calibrate --plot         # the calibration curve (cost matrix, sweep, NP point, AURC) + PNG
python -m eval.noise_floor              # inter-annotator kappa — the noise floor (LLM-persona proxy)
bash scripts/smoke-check.sh             # key-file checks + pytest
```

Evaluation is **cost-aware by design** — prompt caching, the Message Batches API, pre-recorded worker traces, and stratified sampling, with a built-in judge cost/cache meter (`GET /api → judge_cost`). Methodology and targets → **[docs/EVAL.md](docs/EVAL.md)**.

## Stack

Python 3.12 · LangGraph (`interrupt()` HITL + SqliteSaver) · langchain-anthropic (Claude) · FastAPI · SQLite · MCP (FastMCP) · LangSmith · Tailwind-CDN dashboard.

## License

MIT — see [LICENSE](LICENSE).
