# EVAL.md — Cost-Aware Evaluation Methodology

> **Status: plan + targets.** This documents *how* AgentGuard's guardian is evaluated
> and how that evaluation is kept cheap. Numbers marked _TBD_ are filled in only after
> they are **measured** — never asserted. Most of this lands with **Stage 1**
> ([ROADMAP.md](../ROADMAP.md)); the cost meter (layer 1) ships in Stage 0.

Evaluating a guardian against adversarial benchmarks means **thousands of LLM calls**
(AgentDojo ≈ 629 security cases, InjecAgent ≈ 1,054, plus a threshold sweep). Run naively
— full-price, synchronous, re-running the whole agent each iteration — that is slow and
expensive. The methodology below is designed so the eval is **cheap by construction**, and
so the savings are *observable*, not claimed. The competency on display is not "I optimized
costs" — it is "I built an eval framework whose cost I can predict, measure, and explain."

---

## Calibration — the keystone metric set

The thesis: **stopping an agent is commodity; a *calibrated* decision about when to stop is the
product.** Formally this is **selective classification under asymmetric cost with noisy labels**,
and the deliverable is a **curve**, not an accuracy number.

**Tier 1 — built now (`eval/calibrate.py`, `python -m eval.calibrate`):**
- **Asymmetric cost matrix.** Errors are not equal — auto-allowing a dangerous action (a *miss*)
  is catastrophic; escalating a safe one (a *false alarm*) is annoyance. We report **expected
  cost** under an explicit matrix, not accuracy.
- **Risk score + aggressiveness sweep.** The guard emits a 0–100 risk score (deterministic
  rule-derived by default — *coarse, key-free*; finer with the LLM scorer). Sweeping the
  auto-allow-vs-escalate threshold yields the **missed-danger-rate vs false-alarm-rate** curve and
  the **risk–coverage** curve (coverage = auto-decided fraction; AURC summarizes it).
- **Neyman–Pearson point.** The honest spec for a safety gate: *"at ≤X% dangerous-miss rate, the
  false-alarm rate is Y%."* The harness reports the lowest-false-alarm threshold under a target
  miss rate, plus the **cost-minimizing** threshold.

**Tier 2 — cheap rigor:** inter-annotator **kappa** as the *noise floor* is **built**
(`eval/noise_floor.py`, `python -m eval.noise_floor`) — three LLM-persona reviewers label the
set and report Fleiss' κ (≈0.52 on the 125-action hardened set, *moderate* agreement); LLM-persona labels are a **proxy**
for human annotators, reported as such. *Planned:* an **adversarial/evasion set** with the gap
reported; a **policy-as-code CI eval** that fails the build on a safety regression.

**Tier 3 — frontier (articulated, not faked):** **conformal prediction** (distribution-free
abstain-or-act guarantee), **trajectory-level** guarding (the sequence is lethal even when each
action is safe), calibration metrics (ECE/Brier), active-learning labels, mutation testing.

> **Honest framing:** the default scorer is a coarse, deterministic proxy so the curve runs with
> **no API key**; the LLM scorer gives the fine-grained curve for ~a cent. Numbers are *measured*
> against a small hand-labeled set with a stated noise floor — never a single cherry-picked figure.

## Two-tier eval design (the core decision)

Separate the **agent-under-test** (the worker) from the **system-under-test** (the guardian):

| Tier | What runs | Cost | When |
|---|---|---|---|
| **Static replay** | Pre-recorded worker actions → guardian classifies | Guardian tokens only | Every guardian change (the hot loop) |
| **Live run** | Real worker reacting to the guard's decisions | Worker + guardian tokens | Rarely — only for trajectory metrics |

**Why two tiers:** classification metrics (ASR, FPR, per-class accuracy) only need the
*proposed action* — so we record the worker's actions **once** and replay them against the
guardian forever. But **utility-under-attack** (does the agent still finish its task when the
guard intervenes?) genuinely requires a **live worker** that sees the block and adapts — a
replayed trace can't measure it. So: static replay for the fast loop, occasional live runs for
the trajectory numbers. AgentGuard already uses the static-replay shape today
([eval/dataset.jsonl](../eval/dataset.jsonl) is a static action fixture with no live worker).

---

## Cost-optimization layers

### 1. Prompt caching on the guardian judge — *ships in Stage 0; measure, don't assume*
The guardian's stable prefix (classification instructions, output schema, and — later —
few-shot examples) is sent with `cache_control: {"type": "ephemeral"}`
([guardian.py](../agentguard/policy/guardian.py)). Cache reads bill at **0.1×** base.

**Honest caveat:** Anthropic only caches a prefix **above a minimum length** (~1024 tokens
for Sonnet, ~2048 for Haiku). The current guardian prompt is ~400 tokens — **likely below the
threshold, so caching may not engage at all today.** That is precisely why we instrument it
rather than trust it:

- A **cost meter** (`cost_stats()` in [guardian.py](../agentguard/policy/guardian.py),
  surfaced at **`GET /api` → `judge_cost`**) accumulates `input_tokens`, `output_tokens`,
  `cache_creation_tokens`, `cache_read_tokens`, and a derived `cache_hit_rate`.
- If `cache_read_tokens` stays 0 across a run, caching isn't engaging — the fix is to grow the
  stable prefix (e.g. add few-shot examples) past the threshold, where caching *also* starts
  paying off. **Target cache hit rate: ~70% _(TBD — measured, not claimed)_.**

### 2. Message Batches API — *Stage 1, offline eval only*
Eval has no real-time requirement, so submit it as a **batch job**: **50% off** input + output,
24h SLA. The **live system** (`agentguard.api:app`) stays **synchronous** — humans approving
actions need real-time. Batch is for the offline benchmark only. _Caveat:_ cache hits inside a
batch are best-effort (timing varies), so model batch and caching as **additive when they
land**, not a guaranteed multiplication.

### 3. Pre-recorded worker traces — *Stage 1*
Run the worker **once** over AgentDojo / InjecAgent, capture every proposed action as JSONL
(`{attack_id, proposed_action, context, expected_classification}`), then replay against the
guardian. ~10× faster iteration; you only re-spend on the guardian itself. (This is tier-1
above.)

### 4. Model tiering — *a deliberate decision, not a reflex*
- **Worker (agent-under-test):** drop to **Haiku** for eval — it's just a cheap action proposer.
  (Today's default worker is Sonnet, [graph.py](../agentguard/graph.py); cheaper is fine for eval.)
- **Guardian judge:** runs on **every** tool call in production, so a big model per action is a
  real cost/latency tax. Today's default is **Haiku** ([guardian.py](../agentguard/policy/guardian.py)).
  Keep the shipped model honest in the eval — and treat **Haiku-judge vs Sonnet-judge hold rate**
  as an **ablation finding** ("a 5× cheaper judge concedes only X% hold rate"), not a cost compromise.

### 5. Stratified sampling — *Stage 1*
Cut a **50–100 case** sample stratified across attack classes (direct injection, indirect
injection, tool misuse, role manipulation). Run the sample on **every** guardian change; run the
**full** benchmark only when sample metrics improve or before publishing.

### 6. `count_tokens` pre-flight — *Stage 1*
Anthropic's `count_tokens` endpoint is **free**. Call it on the batched payload first and predict
cost before submitting: `cached_prefix × 0.1 × base + fresh_input × base + output × base`, then
`× 0.5` for batch. Catches a runaway eval before it spends anything.

---

## Metrics (cross-ref [ROADMAP.md](../ROADMAP.md) Stage 1)

Never a single accuracy number. Report: **ASR** (targeted + untargeted), **FPR**,
**benign-utility delta** (guard on vs off, attacks off), **utility-under-attack** (needs a
live run), **latency** p50/p95/p99, a **per-attack-class confusion matrix**, and the
**safety/utility Pareto curve** (requires making the guard parametric first).

## Cost observability

- **Built-in:** `GET /api → judge_cost` (the meter above) — live token + cache-hit visibility.
- **LangSmith:** per-run traces of the worker↔guardian loop — already wired via env vars.

## Operational

- **Research credits:** apply early to the Anthropic external-researcher / OpenAI researcher
  programs — this project's profile (AI safety, red-teaming, observability) fits what they fund.
  Worth doing, not to be banked on; verify current program terms.

## Targets (filled in only once measured)

| Metric | Target | Measured |
|---|---|---|
| Guardian cache hit rate | ~70% | _TBD_ |
| Cost per full-benchmark run | < $5 | _TBD_ |
| Naive vs optimized cost reduction | — | _TBD_ |
