# Roadmap

> **Pitch:** *OpenClaw gives agents hands. AgentGuard gives them brakes.*
> The arc from "the brakes work" to "the brakes survive an attacker, act on real machinery, and scale to a fleet."

> **The thesis (what's actually hard):** *Stopping an agent is a framework feature — a brake pedal. Knowing **when** to stop it, and **proving** the decision is calibrated, is the product.* A pause button is plumbing; LangGraph hands it to you for free. What it refuses to answer is whether your approval policy is too paranoid (humans rubber-stamp every alert until the gate is useless) or too lax (something blows up). That line is usually set by vibes. AgentGuard makes the guard's judgment **measurable and tunable** — it's *selective classification under asymmetric cost with noisy labels*, and the deliverable is the **measured false-alarm-vs-missed-danger curve**, not a single accuracy number.
>
> *Anyone can stop an agent. AgentGuard knows when to — and proves it.*

> **★ The research apex — "Oversight Has a Capacity"** (full detail → [`docs/RESEARCH.md`](docs/RESEARCH.md)). The deepest version of the thesis: the human reviewer is not a perfect oracle — they are **subjective** (no ground-truth "safe" label; measured Fleiss' κ ≈ 0.52) and **endogenous** (escalation fatigues them). So the optimal *when-to-escalate* policy is **load-aware**, and realized safety is an **inverted-U**: *more human oversight can make a system **less** safe, and the safety-optimal guard escalates **below** capacity.* This is *selective classification under asymmetric cost with noisy labels **and an endogenous expert*** — the last clause is the novel seam. (Applies only where the label is subjective, e.g. agent oversight — **not** where there's ground truth like banking.)

The MVP is the foundation. Each stage above it adds **one capability** that makes the control plane harder to defeat, more real, or broader in reach. The **calibration of the guard's judgment** (Stage 1) is the moat; everything else is substrate or distribution.

---

## The Arc

| Stage | Theme | What it adds | Why it matters | Status |
|---|---|---|---|---|
| **0 — Foundation** | *Brakes* | Worker + guardian + LangGraph `interrupt()` HITL + audit + eval + **MCP (protocol-native distribution surface)** + dashboard | Nothing executes without classification; risky actions can't run without a human | 🟡 In progress |
| **1 — Calibration & Adversarial Robustness** | *Knowing when to brake, and proving it* | The keystone: a risk score + aggressiveness sweep → the missed-danger-vs-false-alarm curve under an asymmetric cost matrix; a measured noise floor (kappa); adversarial/evasion set; published benchmarks (AgentDojo, InjecAgent) | The moat — selective classification under asymmetric cost with noisy labels; the question LangGraph refuses to answer: "is my policy any good?" | ⬜ Planned (next) |
| **⛓ Enforcement & Interception** | *The gate the agent can't walk around* | The no-bypass ladder: MCP gateway → Claude Code `PreToolUse` hook → (Stage 2) capability/sandbox mediation | An action the guard never sees is unguarded; enforcement = owning the chokepoint, not merely being an MCP option *(cross-cutting, foundational)* | ⬜ Cross-cutting |
| **✦ Notifications & Remote Approval** | *Approve from your pocket* | Notify on pending (push/Slack/WhatsApp/SMS) + approve/reject from your phone | Approval no longer requires sitting at the terminal *(cross-cutting)* | ⬜ After Stage 1 |
| **2 — Real Execution & Sandboxing** | *Brakes on real machinery* | Replace simulated side-effects with real execution inside an isolated sandbox | The firewall contains real damage, not a simulation | ⬜ Planned |
| **3 — Fleet Control Tower** | *Brakes for a fleet* | Supervise N concurrent workers under one policy plane; learned escalation | One policy plane governs many agents — tool becomes platform | ⬜ Future |
| **★ North Star** | *Brakes as a platform* | Hosted, multi-tenant, per-team policy | The productized version of everything above | ⬜ Vision |

---

## Stage 0 — Foundation (MVP) · *the brakes work*

A real worker LLM proposes tool calls; a real guardian (deterministic rules → one LLM judge for the ambiguous middle) classifies each as **safe / approval-required / blocked**; risky actions pause the LangGraph run via `interrupt()` and wait for a human; every decision is audit-logged; a guardian eval prints real metrics; AgentGuard is exposed as an **MCP server** — the policy engine is the server, any MCP-aware agent (Claude Code, Cursor, custom LangGraph) is the client, so adoption is one line of config rather than a LangGraph rewrite. The `interrupt()` loop stays the deep HITL artifact; MCP is the *distribution surface* on top of it, not a replacement.

**Why it matters:** establishes the full control loop — every action is classified, and risky ones cannot execute without a human in the loop. Framing the same engine as protocol-native ("safety layer for any MCP-compatible agent") sharpens positioning without new work.
**Honest limit:** an approval gate on its own is becoming common; the depth, and the differentiation, lives in the stages below. MCP is a transport, not the algorithmic depth — land it *after* the Stage 1 eval, never instead of it.

---

## Stage 1 — Calibration & Adversarial Robustness · *knowing when to brake, and proving it*

**This is the moat.** A gate that pauses is plumbing; a gate whose *judgment* is **measured and tunable** is the product. The frontier framing: **selective classification under asymmetric cost with noisy labels** — and the deliverable is a **curve**, not an accuracy number. The methods are tiered, *keystone* (build first, put on screen) → *frontier* (articulated direction, not faked).

**Tier 1 — the keystone (the chart you put on screen)**
- **Asymmetric cost, not accuracy.** A guard is a cost-asymmetric decision: auto-allowing a dangerous action (a *miss*) is catastrophic; over-flagging a safe one (a *false alarm*) is annoyance. Score by **expected cost** under an explicit cost matrix, never raw accuracy. *(Already past accuracy — the MVP eval reports recall-on-dangerous + precision.)*
- **The aggressiveness dial → risk–coverage curve.** Give the guard a risk score, then sweep the auto-allow-vs-escalate threshold. Plot **missed-danger rate vs false-alarm rate** (safety/utility tradeoff) and **coverage vs error-on-covered** (selective classification; AURC as one number). *"Pick your risk tolerance with data, not vibes."* Prerequisite: make the guard **parametric** (a risk score to threshold) — done in this stage.
- **Neyman–Pearson operating point** — how a real safety gate is specified: *"at a guaranteed ≤X% dangerous-miss rate, the false-positive rate is Y%."*
- **Live calibration dial (built — demo).** The dashboard's "Calibration explorer" replays the saved per-action scores and lets you *drag* the aggressiveness threshold while the miss/false-alarm metrics and 125-action grid recolor in real time — the curve made tangible, client-side, **zero API cost**. (`GET /calibration` + `eval/calibration.json`.)
- **Two-model comparison (built — `eval/compare_models.py`, `model_comparison.png`).** Overlays Haiku vs Sonnet calibration curves: **Sonnet AURC 0.351 vs Haiku 0.373** — a better model helps *modestly*, doesn't solve the hard set. Turns *"would a better model be more reliable?"* into a *shown, model-dependent* result (single seed, temp 0; a published claim runs N seeds + mean ± spread). *Cost framework activates only at benchmark scale (Tier 3);* until then runs are pennies.
- **Simulated inverted-U (built — `eval/inverted_u.py`, `inverted_u.png`).** Models a fatiguing reviewer `r(load)` over the real scored actions; realized danger-through is **U-shaped** — the safety-optimal escalation rate is **64–72% (below full escalation)**, and escalating *everything* is strictly worse. *Modeling, not a human study;* the claim is the shape, not the absolute safety level (the guard is weak on the hard set). This is the headline result of the "Oversight Has a Capacity" thesis, demonstrated.

**Tier 2 — rigor that out-classes the field (cheap, devastatingly honest)**
- **Inter-annotator agreement (the noise floor).** "Is this risky?" is subjective; multiple labelers + Cohen's/Fleiss' **kappa** define the *irreducible* disagreement — a guard at the agreement ceiling is at human level. *Honest caveat:* LLM-persona labels are a **proxy** for the human floor, reported as such.
- **Adversarial / evasion set + report the gap.** Near-boundary cases — obfuscated danger (base64 `rm -rf`, exfil split across steps, secrets hidden in a "config read") and scary-but-benign actions — with the **evasion rate under attack** reported honestly (*"99% on direct danger, 70% obfuscated"*).
- **Policy-as-code regression eval in CI.** Every rule/prompt change re-runs the eval; the build **fails if safety regressed**. The guardrail is treated like code with a test suite.

**Tier 3 — published benchmarks + hardening (dataset weight & robustness)**
- *AgentDojo* (629 security cases) and *InjecAgent* (1,054 indirect-injection cases) wired in as the defense — these mostly stress the **LLM judge**; the curated coding-attack corpus stresses the **rules**.
- **Hardening, measured before/after:** untrusted content quarantined from the guardian's instruction channel; path/command canonicalization; the guardian judges *structured action facts*, never raw attacker prose. A **retrieval/similarity layer** (vector store of known signatures + past blocks) is a deferred graduated tier between rules and judge — and the guard's *memory* for the Stage-3 self-improving loop.

**Tier 4 — frontier**
- **★ The research seam — "Oversight Has a Capacity" (the actual novel contribution; see [`docs/RESEARCH.md`](docs/RESEARCH.md)).** The human reviewer is **endogenous**: escalation fatigues them, so the optimal deferral policy must be **load-aware**, and uncertainty-based deferral is *fatigue-suboptimal*. Buildable now via a **simulated inverted-U** experiment (model `r(load)`, sweep escalation rate, show the optimum is below capacity); fatigue is also an **attack surface** (bury a malicious action in routine ones to induce rubber-stamping). Prior art cited (complementarity / learning-to-defer assume a *static* expert); we claim only the endogenous-expert coupling — **verify before publishing.**
- **Trajectory-level guarding — PRIOR ART we *implement*, not claim** ([Trajectory Guard](https://arxiv.org/pdf/2601.00516), [ShieldAgent](https://arxiv.org/pdf/2503.22738), AgentAuditor): a single action is safe but the *sequence* is lethal (read secret → write public file → push). It's a **detection** layer on the orthogonal "what we inspect" axis — the load-aware oversight layer *consumes* it; the two compose, neither builds on the other.
- **Conformal prediction** — distribution-free abstain-or-act guarantees (easy to misapply; implement only when going deep).
- **Calibration metrics** (ECE / Brier / reliability), an **active-learning** label loop, **mutation testing** for policy robustness.

Cost is kept low by design — see [`docs/EVAL.md`](docs/EVAL.md) (caching · Message Batches · pre-recorded traces · stratified samples · free `count_tokens` pre-flight; observed via the built-in `judge_cost` meter).

**Why it matters:** this is the question LangGraph refuses to answer — *"is my policy any good?"* Measuring precision/recall on a fuzzy, human-judgment task under asymmetric cost is a real ML/safety question almost nobody publishes a measured answer to. It's the senior, ownable, research-flavored wedge — and it's honest.
**Honest limit:** a small hand-labeled set with a *measured* noise floor, reported as such; published benchmarks add weight, the curated corpus is hand-built — never overclaimed. The thesis raises the bar: claiming "calibrated judgment is the product" obliges the curve to exist.

---

## ⛓ Enforcement & Interception Completeness (no-bypass) · *the gate the agent can't walk around*

**Cross-cutting, and the most foundational concern of all.** A control plane is only as
strong as the actions it actually *sees* — an action that never reaches the guardian is, by
definition, unguarded. Being an MCP server gives AgentGuard **reach** (any compatible agent
*can* route through it); it does **not** give **enforcement**. Enforcement comes from
**owning the chokepoint — being the sole path to the capability**, the way a firewall owns the
wire. The **operator** configures this on their *own* agent (they want the brakes); the
guarantee it buys is that the **agent** — including a prompt-injected one — cannot reach a side
effect except through the gate. The threat model is "the agent goes rogue," not "the operator
evades their own safety tool."

**The interception ladder (weak → strong):**

| Level | Mechanism | How the operator wires it | Strength · coverage |
|---|---|---|---|
| **1 · Cooperative** | AgentGuard is one MCP server among many; the agent is *asked* to submit actions | Add AgentGuard to the host's `mcpServers` config | Weak — the agent can call other tools directly |
| **2 · MCP gateway** | AgentGuard is the **only** MCP server the host talks to; the real tool servers sit **behind** it and only approved calls are forwarded | Point the host at AgentGuard alone; list the real servers as AgentGuard's *downstream*, removing their direct host entries | Strong **for MCP tools** — the only path to them |
| **3 · Host hook** | The host calls AgentGuard before **every** tool, built-ins included (e.g. Claude Code `PreToolUse`) | Enable AgentGuard's hook in the host's settings | Strong — *all* tools on that host, MCP or native |
| **4 · Capability / sandbox** | The agent runs sandboxed *without* the real fs / net / deploy capability; AgentGuard mediates the syscall | Run the agent inside AgentGuard's sandbox (Stage 2) | **True no-bypass** — the OS enforces it |

**What it adds**
- A named **threat model** (unseen action = unguarded action) and a concrete enforcement path.
- The demoable headline: **Claude Code gated by a `PreToolUse` hook** (Level 3 — a real, well-known agent that physically cannot act without clearing the gate) and an **MCP gateway** demo (Level 2 — the agent's only door to its tools is AgentGuard).

**Why it matters:** this is the line between a *suggestion* and a *firewall*. No-bypass is the
foundation every other guarantee rests on — robustness, audit, and approval all assume the
action was actually seen.
**Honest limit:** each level only covers what funnels through its chokepoint — an MCP gateway is
blind to the host's *built-in* tools, a host hook is specific to that host, and only
capability/sandbox mediation (Stage 2) is general and complete. Completeness is a ladder you
climb, not a checkbox — and enforcement is *against the agent given the operator configured the
gate*, never something imposed on an unwilling system.

---

## ✦ Notifications & Remote Approval (out-of-band HITL) · *approve from your pocket*

**Cross-cutting capability** — best landed *after* Stage 1, and what makes Stage 3 (fleet) usable at scale. It removes the core friction of human-in-the-loop: *the human has to be at the terminal.*

**What it adds**
- A notification fires the instant an action goes **pending** (push · Slack · WhatsApp · SMS).
- The human **approves or rejects from their phone**; the agent stays paused — or TTL-expires to *deny* — until they respond.
- Any messaging client becomes an approval surface; the dashboard/terminal no longer has to be in front of you.

**Why it's nearly free:** the MVP's `interrupt()` + pending-queue + approve/reject-by-`thread_id` + TTL is *already* an asynchronous, out-of-band approval backbone. This is just **another client on the existing approve/reject API + an outbound notification** — not a re-architecture.

**Why it matters:** it removes the #1 real-world friction of human-in-the-loop — the agent can pause for you while you're anywhere.
**Honest limit:** integration/UX depth, not algorithmic depth — the harder problem stays Stage 1. A reach layer: done after, never instead.

---

## Stage 2 — Real Execution & Sandboxing · *the brakes act on real machinery*

The MVP **simulates** write/shell/git/deploy. This stage makes them real — safely.

**What it adds**
- Side-effecting tools execute for real **inside an isolated sandbox** (Docker → gVisor/Firecracker microVM as the bar rises), so the blast radius is contained.
- The firewall now stops an **actual** `rm -rf`, performs **real** file writes/git ops in the sandbox, and runs approved deploys against a throwaway target.
- Resource and network-egress limits per run; the sandbox is the enforcement boundary, not a mock.

**Why it matters:** the firewall *contains* danger instead of merely *logging* it — the jump from a convincing demo to a system that actually does the thing.
**Honest limit:** single-host sandboxing first; true microVM isolation is the stretch within this stage.

---

## Stage 3 — Fleet Control Tower · *brakes for a fleet*

One guardian policy plane; many workers.

**What it adds**
- Supervise **N concurrent worker agents**; the dashboard becomes a control tower — every agent's live state, pending approvals across the fleet, per-agent audit.
- **Policy-as-data per repo/team**; **a self-improving policy plane** — the guardian closes the loop on its own history rather than staying a static ruleset: it adapts thresholds from the human approve/reject record (which actions a reviewer always waves through vs. always blocks), and a Claude pass reads the audit log + adversarial misses to *propose* new rules and hardening, re-evaluated before they ship. The gate learns from every human decision and every attack it let slip.

**Why it matters:** one policy plane governing many agents is the step from a tool to a platform — and a gate that *improves itself* from its own audit trail is the step from a fixed filter to a control system.
**Prior art:** the meta-agent → target-agent → feedback-agent loop in [SIA](https://github.com/hexo-ai/sia) (a self-improving agent framework) is structurally the same loop. The cross-ecosystem mapping: SIA improves an agent to be better at a *task*; AgentGuard applies the same loop to make the *guard* better at *judging risk* — with the calibration eval's misses and false-alarms as the feedback signal. Same loop, different objective (safety policy, not task performance).

---

## ★ North Star — Brakes as a platform

Hosted, multi-tenant, per-team policy and SSO; an audit/compliance surface; notifications and PR generation. The productized version of everything above. Vision, not a commitment.

---

## Principles (so this reads as engineering, not hype)

- **Real where it's the claim, simulated where it's plumbing** — the multi-agent loop, the `interrupt()` HITL, and (Stage 1+) the adversarial eval are real and non-negotiable; convenience layers are clearly labeled.
- **Fail safe** — unknown action → human review; stalled approval → TTL-expire to *deny*.
- **Local-first** — the engine, audit log, and dashboard run entirely on your machine (SQLite, no SaaS dependency). Every record of a risky agent action stays local by default; any cloud surface is opt-in, never required. The control plane and its evidence trail are yours.
- **Measure, don't assert** — every safety claim ships with an eval number and a baseline; small hand-labeled sets are described as such.
- **Calibration over mechanism** — the pause is commodity; the *measured, tunable* judgment is the product. Safety claims ship as a curve (missed-danger vs false-alarm, expected cost), not a lone accuracy number.
- **Ship each stage standalone** — every stage is demoable on its own and adds exactly one capability.

---

**Related:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/DECISIONS.md`](docs/DECISIONS.md)
