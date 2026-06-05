# Oversight Has a Capacity: Calibrating Agent Guards to a Subjective, Fatiguing Human

> **Status: working draft.** Built from the artifacts in this repo. Numbers are from a small
> hand-labeled set and a *single seed* at temperature 0 — reported as demonstrations, not
> settled results. Companion: [`PAPER.md`](PAPER.md) (skeleton), [`RESEARCH.md`](RESEARCH.md)
> (thesis detail), [`EVAL.md`](EVAL.md) (methodology). Figures live in [`../eval/`](../eval/).

---

## Abstract

As LLM agents begin to take real, irreversible actions — running shell commands, editing files,
deploying code — the standard safety pattern is a human-in-the-loop approval gate: risky actions
pause and wait for a person. We argue the gate is the easy part. The hard, unsolved part is the
*judgment* — deciding **which** actions to stop — and the field evaluates that judgment against
two assumptions that are both false: that there is a ground-truth notion of "risky," and that the
human reviewer is a perfect, infinitely-available oracle. We show, on a hand-labeled set of 125
adversarially-weighted agent actions, that (i) reviewers only *moderately* agree on what is risky
(Fleiss' κ = 0.52), so there is no single correct label; (ii) framing the guard as **selective
classification under asymmetric cost** makes its operating limits measurable, and on hard inputs
the guard cannot safely auto-decide; and (iii) when the reviewer is modeled as **endogenous** —
fatiguing as escalation load grows — realized safety becomes an **inverted-U** in the escalation
rate: *more human oversight can make a system less safe*, and the safety-optimal guard escalates
**below** the reviewer's capacity. Our contribution is the *measurement framework* and the
endogenous-reviewer result; trajectory-level guarding and learning-to-defer are prior art we cite,
not claim. The inverted-U is a modeling result that motivates a human study; the framework is what
turns "is my guard good?" from a guess into a number.

---

## 1. Introduction

AI coding agents are moving from *suggesting* code to *executing* it. Once an agent can `deploy`,
`rm -rf`, push to `main`, or read a secret, a single bad instruction has real, sometimes
irreversible consequences. The de-facto safety response, echoed across agent frameworks, is a
**human-in-the-loop (HITL) approval gate**: classify each proposed action, and pause the risky
ones for a human to approve or reject.

The gate is commodity. Frameworks hand you the pause primitive (e.g. LangGraph's `interrupt()`)
for free. What no framework tells you is whether your approval *policy* is any good — whether it
is too paranoid (so humans rubber-stamp every alert until the gate is theater) or too lax (so
something blows up). That decision is usually set by intuition.

This paper treats the decision as a measurable problem, and in doing so surfaces a deeper one. The
field implicitly assumes:

1. **a ground-truth label** — that "is this action too risky to auto-run?" has a correct answer;
2. **a perfect human** — that the reviewer the gate escalates to is always available and always
   reliable.

Both are false. "Risky?" is a subjective judgment that depends on context and risk tolerance, and
human reviewers *fatigue*: every escalation spends attention and nudges them toward rubber-stamping
(a well-documented "approval fatigue" failure mode). Crucially, the reviewer is **endogenous** —
the guard's own escalation policy degrades the very oracle it escalates to.

**Contributions.**
- A **measurement framework** that treats an agent guard as *selective classification under
  asymmetric cost* and reports an operating-point curve, a Neyman–Pearson point, and an AURC,
  rather than an accuracy number (§4, §5.1).
- A **measured noise floor**: on 125 hand-labeled actions, reviewer agreement is only moderate
  (Fleiss' κ = 0.52), establishing that there is no single ground-truth safety label (§5.2).
- The **endogenous-reviewer result**: modeling reviewer reliability as decreasing in escalation
  load yields an **inverted-U** — realized safety is maximized at an escalation rate *below*
  capacity, and escalating everything is strictly worse (§5.3).
- A demonstration that results are **model-dependent** and that the framework *measures* that
  dependence (Haiku vs Sonnet, §5.4).

**Scope (stated up front).** This matters where the judgment is genuinely *subjective with delayed
outcomes* — autonomous agent action-gating, content-moderation borderline calls, security-alert
triage. It does **not** apply where there is objective ground truth (e.g. banking-fraud, eventually
verifiable): there you simply measure both parties against the truth and use the better predictor.
Naming the boundary is part of the claim.

---

## 2. Related Work

**Agent guardrails and trajectory-level safety.** A growing body of work guards *agent action
sequences*: Trajectory Guard [1] for real-time anomaly detection over agent trajectories,
ShieldAgent [2] for verifiable safety-policy reasoning over action trajectories, ToolSafe [3] for
step-level tool-invocation guardrails, plus benchmarks such as AgentHarm [4] and trajectory-level
evaluators (AgentAuditor). **We implement per-action gating and treat trajectory-level guarding as
prior art**; our contribution is orthogonal — the *oversight-calibration* layer, which consumes
whatever detection signal exists.

**Learning to defer and human–AI complementarity.** A mature line studies *when* to defer to a
human and how to *complement* human weaknesses: learning to defer [5], learning predictors that
complement humans [6], learning when to require feedback [7], complementary team performance [8],
and appropriate reliance [9]. These assume a **static** expert — available and constant-quality.
Our departure is the **endogenous** expert whose reliability degrades with cumulative load.

**Selective classification and calibration.** Risk–coverage curves and AURC come from selective
classification [10]; distribution-free guarantees from conformal prediction [11]; calibration is
classically measured with ECE/Brier/reliability diagrams. We use the selective-classification lens;
we do *not* yet claim formal calibration (ECE) — that is future rigor.

**Human oversight and approval fatigue.** That reviewers rubber-stamp under load is widely
documented in practitioner and regulatory writing (approval/confirmation fatigue; EU human-
oversight guidance [12]). To our knowledge this is *named* qualitatively but not *formalized inside
the guard's objective*. That formalization — and the inverted-U it produces — is the seam we claim
(and flag for verification before publication).

---

## 3. Problem Formulation

An agent proposes actions; a guard decides, per action `a`, between **auto-allow** and **escalate**
(to a human). Let:

- `s(a) ∈ [0,100]` — the guard's **risk score** (live, from rules or an LLM scorer).
- The **label** for `a` is not a point but a *distribution over reviewers* — different reviewers
  disagree (§5.2). We use a gold label `y(a) ∈ {SAFE, APPROVAL, BLOCKED}` for measurement, with
  the noise floor quantifying its contestability.
- A threshold `θ`: auto-allow iff `s(a) < θ`, else escalate.
- An **asymmetric cost** `C[y][decision]`: auto-allowing a dangerous action (a *miss*) is
  catastrophic; escalating a safe one (a *false alarm*) is annoyance (Table 1).
- A **reviewer model** `h(a, ℓ)` with reliability `r(ℓ)` that *decreases* in cumulative escalation
  load `ℓ`. This is the endogenous element: `ℓ` is driven by the guard's own escalation rate.

The objective is to minimize **expected realized cost — including human-fatigue-induced errors** —
not classification accuracy. The novelty is that `r` depends on the policy's escalation history (a
closed loop), so the optimal `θ` is **load-aware**.

**Table 1 — asymmetric cost (gold × decision).**

| gold | auto-allow | escalate |
|---|---:|---:|
| SAFE | 0 | 1 (false alarm) |
| APPROVAL | 5 | 0 |
| BLOCKED | 50 (catastrophe) | 1 |

---

## 4. Methods

**Dataset.** 125 hand-labeled agent actions (`eval/dataset.jsonl`), deliberately weighted to *hard*
cases: 54 ambiguous-middle (e.g. `npm install <pkg>`, edit `package.json`, `git rebase`, deploy to
*staging*), 23 obfuscated/adversarial (base64-encoded `rm -rf`, homoglyph `maín`, path traversal,
secret exfiltration, pipe-to-shell), and 16 scary-but-benign false-alarm traps (`rm -rf
node_modules`, read `.env.example`). Labels: SAFE 42 / APPROVAL 52 / BLOCKED 31. A small, curated
set — reported as such, not a published benchmark.

**Guard scorer.** Deterministic rules score clear cases for free; the ambiguous middle is scored by
an LLM (Haiku by default, Sonnet for comparison), at temperature 0, prompted for a 0–100 risk
integer. Scores are persisted so analyses replay them without re-querying.

**Calibration.** We sweep `θ` and report, per operating point: missed-danger rate, false-alarm
rate, coverage, and expected cost; we extract the cost-minimizing point, the Neyman–Pearson point
(lowest false-alarm at 0% miss), and the area under the risk–coverage curve (AURC). (`eval/
calibrate.py`.)

**Noise floor.** Three reviewer *personas* (cautious / pragmatic / strict-compliance) label the set;
we compute pairwise Cohen's κ and overall Fleiss' κ. **These are LLM personas — a proxy for human
annotators, reported as such.** (`eval/noise_floor.py`.)

**Endogenous-reviewer simulation.** We model reviewer reliability
`r(ℓ) = max(r_min, 1 − slope·max(0, ℓ − C))` with capacity `C`, `slope = 0.02`, `r_min = 0.2`: the
reviewer is reliable up to `C` reviews, then degrades. For each `θ`, auto-allowed dangerous actions
are guard-misses; escalated dangerous actions are missed with probability `1 − r(ℓ)` at their load
position. We sweep `θ` (hence the escalation rate) and vary `C`. **This models a documented
phenomenon; it is not a human study.** (`eval/inverted_u.py`.)

---

## 5. Experiments and Results

### 5.1 The guard's judgment is measurable — and limited on hard inputs

![Calibration curve](../eval/calibration.png)

On the 125-action set the guard's safety/utility tradeoff is a real curve, not a binary. Under the
asymmetric cost (Table 1), the **cost-minimizing policy collapses to "escalate almost everything"**:
reaching 0% missed-danger requires a ~100% false-alarm rate, and the AURC is 0.37 (vs 0.28 on an
easier 30-row pilot set — harder inputs, worse separation). The reading is not "the guard is bad";
it is that *on adversarial/ambiguous inputs this guard cannot safely auto-decide*, so it is forced
to lean on the human. That dependence is precisely what makes the reviewer's properties decisive.

### 5.2 There is no single ground truth (noise floor)

Three persona reviewers labeling the same 125 actions reach only **Fleiss' κ = 0.52** (moderate
agreement). Pairwise Cohen's κ ranges from 0.42 (cautious vs pragmatic) to 0.71 (cautious vs
compliance); the *pragmatic* reviewer labels 87 actions SAFE versus the cautious reviewer's 45 —
the disagreement is concentrated on the risk-tolerance axis, exactly the contested middle. The
persona majority matches the gold label 74% of the time. A guard cannot be scored against one
objective truth; the agreement ceiling is the honest yardstick. *(Personas are a proxy for human
annotators.)*

### 5.3 Oversight has a capacity (the inverted-U)

![Inverted-U](../eval/inverted_u.png)

Modeling the reviewer as endogenous flips the usual intuition. As the guard escalates *more*, two
failure modes trade off: escalate too little and the guard auto-allows danger (guard-misses);
escalate too much and the reviewer overloads and rubber-stamps (fatigue-misses). Realized
danger-through is therefore **U-shaped in the escalation rate** — and the safety-optimal escalation
rate is **below full escalation**:

| reviewer capacity | optimal escalation rate | danger-through at optimum | danger-through escalating *everything* |
|---|---:|---:|---:|
| 10 | 64% | 56% | 69% |
| 25 | 64% | 42% | 57% |
| 50 | 72% | 22% | 39% |

**Escalating everything is strictly worse than the optimum**, and the optimum shifts with capacity.
The absolute danger-through is high because the guard is weak on this hard set (§5.1) — the claim is
the *shape* (more oversight → less safety past the optimum), not the level. This is a *modeling*
result; a human study fitting `r(ℓ)` (future work) would make it empirical.

### 5.4 The result is model-dependent — and we measure it

![Two-model comparison](../eval/model_comparison.png)

Re-scoring with a stronger model shifts the curve: **Sonnet AURC 0.351 vs Haiku 0.373**, and Sonnet
can safely auto-allow a sliver (cost-min `θ`=10) where Haiku must escalate everything (`θ`=0). The
gain is *modest* — a better model helps but does not solve the hard set. The point is methodological:
guard quality depends on the scoring model (and threshold, and attack mix), so the right output is
not "guards are good/bad" but *a measurement, for a given configuration*. (Single seed, temperature
0; a published claim should run N seeds and report mean ± spread.)

---

## 6. Limitations

- **Small, curated dataset** (125 actions), single domain (coding-agent actions); results are
  demonstrations of the *instrument*, not population estimates.
- **Personas are a proxy** for human annotators; the κ = 0.52 floor is an estimate, not the true
  human-agreement ceiling.
- **The inverted-U is simulated**, not measured: fatigue is documented, but `r(ℓ)`'s shape is
  assumed, not fit to people.
- **Single seed, temperature 0**; LLM scores carry residual nondeterminism not yet quantified.
- **Operating-point analysis, not formal calibration** (no ECE/reliability yet).
- The endogenous-reviewer framing's **novelty is unverified** against the deferral literature —
  flagged for a citation pass before any publication claim.

---

## 7. Future Work

Fit `r(ℓ)` from a **human study** (the empirical grounding); a **load-aware deferral policy** that
escalates by *expected value of review* rather than uncertainty alone; a **fatigue-as-attack**
evaluation (bury a malicious action in a routine stream to induce rubber-stamping; show the
load-aware policy resists it); **N-seed** runs with variance; formal **calibration metrics** and
**conformal** abstention; and scaling to **published benchmarks** (AgentDojo, InjecAgent).

---

## 8. Ethical Considerations

The framing here is **decision support for the operator**, not replacement of human authority. A
natural extension — measured comparative reliability leading the human to *delegate* certain
decision categories to the guard — must be **consent-based, revocable, and category-scoped**: the
operator chooses, with data, and can revoke. We explicitly avoid any framing in which an agent
overrides a person's judgment without consent. The fatigue result also has a defensive reading:
because rubber-stamping is exploitable, modeling it is a step toward *protecting* reviewers, not
automating them away.

---

## 9. Conclusion

Stopping an agent is a framework feature. Knowing *when* to stop it — and accounting for the fact
that asking depletes the human you are asking — is the problem. Treating the guard as selective
classification under asymmetric cost makes its judgment measurable; measuring reviewer agreement
shows there is no single ground truth; and modeling the reviewer as endogenous shows that oversight
has a capacity, beyond which more of it makes a system less safe. The numbers here are small and
some are simulated, and we say so. The framework is the contribution: it turns "is my guard any
good?" from a vibe into a curve.

---

## References

[1] *Trajectory Guard: A Lightweight, Sequence-Aware Model for Real-Time Anomaly Detection in
Agentic AI.* arXiv:2601.00516.
[2] *ShieldAgent: Shielding Agents via Verifiable Safety Policy Reasoning.* arXiv:2503.22738.
[3] *ToolSafe: Enhancing Tool Invocation Safety of LLM-based Agents via Proactive Step-level
Guardrail and Feedback.* arXiv:2601.10156.
[4] *AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents.*
[5] Madras, Pitassi, Zemel. *Predict Responsibly: Improving Fairness and Accuracy by Learning to
Defer.* NeurIPS 2018.
[6] *Sample-Efficient Learning of Predictors that Complement Humans.* arXiv:2207.09584.
[7] *To Ask or Not to Ask: Learning to Require Human Feedback.* arXiv:2510.08314.
[8] *Complementarity in Human-AI Collaboration: Concept, Sources, and Evidence.* arXiv:2404.00029.
[9] *Towards Effective Human-AI Decision-Making: The Role of Human Learning in Appropriate
Reliance on AI Advice.* arXiv:2310.02108.
[10] Geifman, El-Yaniv. *Selective Classification for Deep Neural Networks.*
[11] Angelopoulos, Bates. *A Gentle Introduction to Conformal Prediction and Distribution-Free
Uncertainty Quantification.*
[12] European Data Protection Supervisor. *TechDispatch #2/2025: Human Oversight of Automated
Decision-Making.*
