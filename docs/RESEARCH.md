# RESEARCH.md — research direction & paper plan

> The detailed, load-bearing version of the thesis. The README/ROADMAP carry short
> pointers; the full reasoning, prior art, scope boundaries, and experiment plan live
> here so nothing important is lost.

---

## The thesis — "Oversight Has a Capacity"

Agent safety is almost always modeled as a **perfect, infinite human** checking a
**fallible agent** against a **ground-truth** notion of "safe." All three assumptions are
false, and the failure of all three is the contribution:

1. **No ground truth.** "Is this action too risky to auto-run?" is a *subjective* judgment;
   even careful reviewers disagree. We measure it — Fleiss' κ ≈ 0.53 (*moderate* agreement)
   on our set (`eval/noise_floor.py`). There is no single correct safety label.
2. **The human is finite and fatiguing.** Every escalation spends attention and nudges the
   reviewer toward rubber-stamping. The reviewer is **endogenous** to the system: the guard's
   own escalation policy *degrades the very oracle it escalates to.*
3. **Asymmetric, delayed cost.** A *miss* (auto-allowing danger) is catastrophic; a *false
   alarm* is annoyance; outcomes arrive late and rarely.

**Claim.** Because the expert is endogenous, the optimal *when-to-escalate* policy must be
**load-aware**. Uncertainty-based deferral (ask whenever unsure) is **fatigue-suboptimal** —
past a load threshold you should *not* escalate a high-uncertainty case, because the depleted
human decides it *worse* than the calibrated guard would alone. Realized safety is an
**inverted-U** in escalation rate: too little (danger auto-runs) *and* too much (rubber-
stamping) both reduce safety.

> **The headline result:** *more human oversight can make a system **less** safe, and the
> safety-optimal guard escalates **below** the human's nominal capacity.*

One-line framing: **selective classification under asymmetric cost with noisy labels *and an
endogenous expert.*** The last clause is the new part.

---

## What is NOT novel (claim only the seam)

We were burned twice assuming obvious-sounding frontiers were virgin territory. They weren't.
State prior art plainly and claim only the narrow seam:

- **Trajectory / sequence-level guarding — PRIOR ART. We *implement* it; we do not claim it.**
  [Trajectory Guard](https://arxiv.org/pdf/2601.00516), [ShieldAgent](https://arxiv.org/pdf/2503.22738),
  [ToolSafe](https://arxiv.org/html/2601.10156v1), AgentAuditor, [AgentHarm](https://www.emergentmind.com/topics/agentharm).
- **Human-AI complementarity / learning-to-defer / learning-to-complement / selective
  oversight — PRIOR ART, cited.** [Complement-Humans](https://arxiv.org/pdf/2207.09584),
  [To Ask or Not to Ask](https://arxiv.org/html/2510.08314),
  [Complementarity survey](https://arxiv.org/html/2404.00029v1),
  [Appropriate Reliance](https://arxiv.org/abs/2310.02108),
  [EU human-oversight guidance](https://www.edps.europa.eu/data-protection/our-work/publications/techdispatch/2025-09-23-techdispatch-22025-human-oversight-automated-making_en).
  These learn *who is better* and *when to ask* — but assume a **static** expert.
- **The seam we claim (verify before publishing):** the expert is **endogenous** — reliability
  degrades with cumulative escalation load — so the optimal deferral policy is **load-aware**,
  and uncertainty-optimal deferral is fatigue-suboptimal. *Before claiming novelty, search:*
  "endogenous expert reliability", "fatigue learning to defer", "load-aware deferral",
  "attention budget human oversight", and [Science of AI Agent Reliability](https://arxiv.org/html/2602.16666v1).

---

## Two orthogonal axes (keep them separate)

The paper stays clear only if these are not conflated:

| Axis | Question | Status |
|---|---|---|
| **Detection granularity** | *What* do we inspect — a single action or the whole trajectory? | **Prior art** (trajectory guarding). We implement/consume it. |
| **Oversight calibration** | *When/whether* to escalate, and *who* is reliable, given a subjective label and a fatiguing human | **The novel contribution.** |

They **compose**: the load-aware oversight layer sits on top of *any* detection layer. The
fatigue thesis does **not** "build on" trajectory guarding — it is a different axis that
*consumes* whatever detection signal exists.

---

## Applicability & scope — DO NOT FORGET

The single sharpest test of whether this is real: *where does it apply, and where is it
pointless?*

- **NOT applicable / not interesting where there is objective ground truth** — e.g.
  **banking fraud** (eventually verifiable). There you simply measure both parties against the
  truth and use the better predictor (usually the model). No "is the human an oracle?" drama,
  no inverted-U worth studying. **Naming this boundary sharpens the paper — say it explicitly.**
- **Applicable where the judgment is inherently subjective with delayed, asymmetric outcomes:**
  autonomous **agent action-gating** (our domain), content-moderation borderline calls,
  security-alert triage, medical-triage judgment calls.
- **The hard part is measurement.** With no ground-truth label, reliability is estimated
  *indirectly* — **inter-rater disagreement** (the noise floor), **longitudinal outcomes** (did
  harm actually occur / was a block needless), and the **asymmetric cost**. That indirection is
  itself part of the contribution.

---

## The experiment (buildable now → human study later)

1. **Simulated inverted-U (key-light, do first).** Model reviewer reliability `r(load)` as a
   decreasing function (degrading sharply once load > capacity). Over the (scaled, hardened)
   dataset, sweep the guard's escalation rate; compute realized safety as
   `f(guard misses + human-fatigue-induced misses)` under the asymmetric cost. Show the
   inverted-U and that the optimum is **below** capacity. Vary the fatigue curve → the optimum
   moves (and we can measure how much).
2. **Load-aware vs uncertainty-only deferral.** Compare escalating by uncertainty alone vs a
   policy that also accounts for remaining attention budget. Show load-aware yields higher
   realized safety at equal human load.
3. **Fatigue as an attack surface.** Simulate an adversary burying one malicious action in a
   stream of routine ones to induce rubber-stamping; show the uncertainty-only policy is
   exploitable and the load-aware one is more robust.
4. **Human study (future work).** Fit `r(load)` from real reviewers — the empirical grounding
   that turns the simulated result into a measured one.

Prerequisite, shared with everything else: **scale + harden the dataset** (more, and crucially
*harder / adversarial / ambiguous* cases — not more obvious ones). A 30-row mostly-obvious set
demonstrates the *instrument*, not a result.

---

## Product angle (optional, MCP-deliverable)

**"Attention-aware escalation":** a guard that learns where human review measurably adds value
and **stops escalating where it doesn't**, preserving the reviewer's scarce attention for the
cases that matter — curing alarm fatigue *with data* rather than vibes. Consent-based and
revocable.

> The provocative "agent overrides human cognition / Neuralink" framing stays a **vision
> footnote**, never the core — and is reframed responsibly as **consented, revocable,
> category-scoped delegation of authority** (the human *chooses*, with data, and can revoke),
> not "the agent overrides your brain." The latter framing is both ethically fraught and a
> credibility risk in a serious venue.

---

## Honest discipline (so we don't repeat the over-claim)

- **Novel paradigms are rare; you do not need one.** A strong contribution is *rigorous
  execution + one genuine seam*, not a revolution. We have both — the calibration-under-
  asymmetric-cost framework (built) + the load-aware / endogenous-expert seam.
- Every claim ships with **prior-art citations** and either a **measured number** or an explicit
  **"future work."**
- The current dataset is **small (30 rows) and honestly labeled as such**; current results are
  *method demonstrations* until the dataset is scaled and hardened.
- Stop digging for a bigger earthquake. **Land this one.**
