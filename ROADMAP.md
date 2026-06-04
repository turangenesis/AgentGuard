# Roadmap

> **Pitch:** *OpenClaw gives agents hands. AgentGuard gives them brakes.*
> The arc from "the brakes work" to "the brakes survive an attacker, act on real machinery, and scale to a fleet."

The MVP is the foundation. Each stage above it adds **one capability** that makes the control plane harder to defeat, more real, or broader in reach.

---

## The Arc

| Stage | Theme | What it adds | Why it matters | Status |
|---|---|---|---|---|
| **0 — Foundation** | *Brakes* | Worker + guardian + LangGraph `interrupt()` HITL + audit + eval + **MCP (protocol-native distribution surface)** + dashboard | Nothing executes without classification; risky actions can't run without a human | 🟡 In progress |
| **1 — Adversarial Robustness** | *Brakes that survive an attacker* | Red-team the guardian against published benchmarks (AgentDojo, InjecAgent) + a curated command-injection corpus; hardening; a two-axis ASR/FPR security eval with the safety-utility Pareto curve | A policy layer that can't be talked into approving danger — the hard, open part of agent safety | ⬜ Planned (next) |
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

## Stage 1 — Adversarial Robustness · *the brakes survive an attacker*

A gate is only as good as its resistance to being talked around. This stage **attacks the guardian** and measures whether it holds — against **published benchmarks**, not just a hand-rolled set.

**What it adds**
- **Published attack benchmarks**, wired in by adapting AgentGuard as the detector/defense each harness already supports:
  - *AgentDojo* — 97 user tasks · 629 security cases across banking / Slack / travel / workspace.
  - *InjecAgent* — 1,054 indirect prompt-injection cases (finance / smart-home / email).
  - These domains aren't coding, so the **deterministic rules rarely fire** — these benchmarks primarily stress-test the **LLM judge** layer.
- A **curated command-injection corpus** (`eval/adversarial/`, ~50–100 cases sourced from public agent incidents — Replit DB delete, Cursor leaks — and bug-bounty writeups). This is the half that **tests the deterministic rules** (`rm -rf` via base64 / variable-indirection / homoglyphs, secret exfiltration disguised as a read, guardian-manipulation prose, context smuggling). The curation itself is a portfolio artifact.
- **Hardening, measured before/after:** untrusted content quarantined from the guardian's instruction channel; path/command canonicalization before rule-matching; the guardian judges *structured action facts*, never raw attacker prose.
- A **two-axis security eval report** — never a single accuracy number:
  - *Attack Success Rate* (ASR), targeted **and** untargeted.
  - *Benign utility* delta — run the benchmark with attacks off, guard on vs off; the gap is the guard's tax on real work.
  - *Utility-under-attack* — task completion when injections are present.
  - *False Positive Rate* — safe actions wrongly blocked (the metric demo-builders hide).
  - *Latency overhead* — p50 / p95 / p99 of the guard decision, not a single number.
  - *Per-attack-class confusion matrix* — where it fails, not just that it fails.
- **The safety/utility Pareto curve** — sweep guard aggressiveness, plot ASR and FPR together, show the frontier. *Prerequisite:* the guard must first be made **parametric** (e.g. a judge confidence score to threshold, or a tunable fail-safe default) — today's verdict is categorical, with no dial to sweep.
- **A cost-aware eval harness** (see [`docs/EVAL.md`](docs/EVAL.md)) — two-tier design (static guardian replay vs. occasional live runs), prompt caching, the Message Batches API (offline only), pre-recorded worker traces, model tiering, and stratified sampling, with cost predicted via free `count_tokens` and observed via the built-in `judge_cost` meter. Thousands of attack cases evaluated for a *predicted, measured* cost — not a naive full-price run.

**Why it matters:** a policy layer that resists being socially-engineered into approving danger is the hard, still-open problem in agent safety — the difference between *gating* actions and *withstanding an adversary*. Reporting the safety/utility frontier (not a lone block-rate) is the difference between "97% blocked" and showing what that 97% costs.
**Honest limit:** published benchmarks (AgentDojo, InjecAgent) carry weight; the curated command-injection set is hand-built and reported as such, never overclaimed.

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
- **Policy-as-data per repo/team**; **learned escalation** — the guardian adapts thresholds from the human approve/reject history (which actions a reviewer always approves vs. always blocks).

**Why it matters:** one policy plane governing many agents is the step from a tool to a platform.

---

## ★ North Star — Brakes as a platform

Hosted, multi-tenant, per-team policy and SSO; an audit/compliance surface; notifications and PR generation. The productized version of everything above. Vision, not a commitment.

---

## Principles (so this reads as engineering, not hype)

- **Real where it's the claim, simulated where it's plumbing** — the multi-agent loop, the `interrupt()` HITL, and (Stage 1+) the adversarial eval are real and non-negotiable; convenience layers are clearly labeled.
- **Fail safe** — unknown action → human review; stalled approval → TTL-expire to *deny*.
- **Measure, don't assert** — every safety claim ships with an eval number and a baseline; small hand-labeled sets are described as such.
- **Ship each stage standalone** — every stage is demoable on its own and adds exactly one capability.

---

**Related:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/DECISIONS.md`](docs/DECISIONS.md)
