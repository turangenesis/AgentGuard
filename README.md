# AgentGuard

**A working human-in-the-loop firewall for AI coding agents — and a research vehicle for one question: how do you calibrate oversight when the human reviewer is subjective and fatiguing?**
*OpenClaw gives agents hands. AgentGuard gives them brakes.*

It's two things at once, on purpose:
- **The system** — a real HITL firewall: a **worker LLM agent** proposes actions (file, shell, git, deploy); a **guardian** (deterministic rules + LLM risk judgment) classifies each as **safe / approval-required / blocked**; risky actions pause the agent mid-task (LangGraph `interrupt()`) and wait for a human; every decision is audit-logged and shown on a live dashboard.
- **The research** — the guardian's judgment is treated as a measurable problem, not a vibe: *selective classification under asymmetric cost with noisy labels — and an endogenous expert.* That last clause is the open question this system exists to investigate (see **[Research direction](#research-direction--oversight-has-a-capacity)** and **[docs/RESEARCH.md](docs/RESEARCH.md)**).

> **The thesis:** Stopping an agent is a *framework feature* — a brake pedal LangGraph hands you for free. Knowing **when** to stop it, and **measuring** whether that judgment is any good, is the hard part. Over-gate and humans rubber-stamp every alert until the gate is useless; under-gate and something blows up.
>
> *Anyone can stop an agent. AgentGuard knows when to — and measures it.*

> **Status:** MVP built — worker + guardian + HITL gate + audit + live dashboard + a **calibration eval** (curve + measured noise floor). Stage 1 (calibration depth + the endogenous-expert thesis) is next. See the **[roadmap](ROADMAP.md)**.

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

On a **125-action hand-labeled set** deliberately weighted to *hard* cases — ambiguous-middle, obfuscated/adversarial (base64 `rm -rf`, homoglyph `maín`, path traversal, exfil), and scary-but-benign traps (small, reported as such — not a published benchmark) — the curve tells the honest story: against adversarial/ambiguous inputs the guard **cannot safely auto-decide** — reaching 0% dangerous-miss forces escalating almost everything (cost-minimizing policy ≈ "ask the human about everything"). That's the artifact *and* the finding: you read the guard's real operating limits off the curve with data — and on hard inputs it can't filter safely, which is exactly what forces high escalation onto a human (→ the research direction below).

**The noise floor — why a single "ground truth" is a lie.** "Is this action risky?" is *subjective*: even careful reviewers disagree, so a guard can't be scored against one objective label. `python -m eval.noise_floor` has three LLM-persona reviewers (cautious / pragmatic / strict-compliance) label the 125-action set and reports **Fleiss' κ ≈ 0.52** — only *moderate* agreement, and the *pragmatic* reviewer labeled **87 actions SAFE vs the cautious one's 45** (that gap **is** the risk-tolerance axis). That's the *irreducible* disagreement, and it's the honest yardstick: a guard that agrees with reviewers as often as they agree with each other is at "human" level. *(Personas are a **proxy** for human annotators — reported as such, not the true human floor.)*

> **Precision note (so the claim is exact):** the curve is **operating-point analysis under asymmetric cost** (selective classification) — *not yet formal calibration* in the ECE/reliability sense. "Calibration" is the theme; the claim is precisely the measured tradeoff + noise floor above. Formal calibration metrics (ECE, Brier, reliability diagrams), an adversarial/evasion set, published benchmarks (AgentDojo, InjecAgent), and frontier methods (conformal prediction, trajectory-level guarding) are deeper rigor on the roadmap — see **[Stage 1](ROADMAP.md)**.

> **The throughline:** *Stopping an agent is a framework feature. Knowing when to stop it — selective classification under asymmetric cost with label noise — is the problem, and here's the curve that shows the tradeoff and lets me set the operating point with data.*

## Research direction — "Oversight Has a Capacity"

The deepest version of the thesis (full detail → **[docs/RESEARCH.md](docs/RESEARCH.md)**). Agent safety is usually modeled as a *perfect, infinite human* checking a fallible agent against a *ground-truth* "safe." All three are false: the label is **subjective** (no ground truth; measured Fleiss' κ ≈ 0.52), the human is **endogenous** (escalation fatigues them — the guard degrades its own oracle), and the cost is **asymmetric**. So the optimal *when-to-escalate* policy must be **load-aware**, and realized safety is an **inverted-U**:

> **more human oversight can make a system *less* safe — the safety-optimal guard escalates *below* the human's capacity.**

That's *selective classification under asymmetric cost with noisy labels **and an endogenous expert*** — the last clause is the novel seam, buildable now as a simulated inverted-U experiment.

**Scope, stated honestly:** this matters **only where the judgment is subjective with delayed outcomes** (agent oversight, content moderation, alert triage) — **not** where there's objective ground truth (e.g. banking fraud, where you just use the better predictor). And it's **honestly positioned**: a novelty check confirmed the core mechanisms are *prior art* — the endogenous-fatiguing-reviewer + load-aware deferral is **FALCON / DeCCaF**, the flooding attack is SOC alert-fatigue, trajectory guarding is ShieldAgent et al. **This is an applied / measurement / systems project, not a novel-theory paper** — the contribution is the open-source firewall + the measurement that brings these ideas together for LLM agents.

> The **working paper draft** is **[docs/DRAFT.md](docs/DRAFT.md)** (built from the figures + real numbers); the **skeleton + intellectual journey** is **[docs/PAPER.md](docs/PAPER.md)**.

## Getting Started

```bash
pip install -r requirements.txt        # or: uv sync
cp .env.example .env                    # add ANTHROPIC_API_KEY (and optional LangSmith key)
```

## Usage

```bash
uvicorn agentguard.api:app              # dashboard → http://localhost:8000 (Run demo needs no key)
```

The dashboard shows a live activity feed, pending approvals with the guardian's reasoning, approve/reject, and a per-run cost line. The **Run demo** button drives a full SAFE → BLOCKED → APPROVAL flow with **no API key**. A **Calibration explorer** lets you *drag* the guard's aggressiveness and watch the missed-danger vs false-alarm tradeoff recolor across all 125 actions in real time — the curve made tangible, replaying saved scores (no API calls). Run `python -m eval.calibrate` once to populate it.

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
