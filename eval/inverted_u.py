"""The headline experiment — simulated inverted-U under an ENDOGENOUS (fatiguing) reviewer.

This is a **modeling / simulation** result, NOT a human study (labeled as such). It reuses the
real 125 scored actions (`calibration.json`) and adds a modeled human whose reliability
`r(load)` *degrades* once cumulative escalation load exceeds a capacity. The phenomenon
(approval/confirmation fatigue → rubber-stamping) is documented; we model its shape and
simulate the consequence.

Result to show: as the guard escalates *more*, two failure modes trade off — auto-allowing
danger (guard misses) vs overloading the human (fatigue misses) — so realized danger-through is
**U-shaped in the escalation rate** (safety is an inverted-U). The safety-optimal escalation rate
is **below full escalation**, and it **moves** as capacity changes. A real human study (future
work) would fit `r(load)`; here we vary it to show the result is structural, not a single curve.

Run:  python -m eval.inverted_u   (key-free — replays saved scores)
"""

from __future__ import annotations

import json
from pathlib import Path

CALIB = Path(__file__).resolve().parent / "calibration.json"
OUT = Path(__file__).resolve().parent / "inverted_u.json"
PNG = Path(__file__).resolve().parent / "inverted_u.png"

_DANGER = {"APPROVAL_REQUIRED", "BLOCKED"}
THRESHOLDS = list(range(0, 105, 5))
CAPACITIES = [10, 25, 50]  # how many reviews before the human starts to fatigue


def reliability(load: int, capacity: int, slope: float = 0.02, r_min: float = 0.2) -> float:
    """Reviewer reliability vs cumulative escalation load: ~perfect up to `capacity`, then it
    decays linearly toward `r_min` (a fatigued reviewer rubber-stamps, i.e. misses danger)."""
    return max(r_min, 1.0 - max(0, load - capacity) * slope)


def simulate(actions: list[dict], theta: int, capacity: int) -> dict:
    """One operating point: guard auto-allows score<θ, escalates the rest to a fatiguing human.

    A dangerous action that is auto-allowed is a guard-miss; a dangerous action reviewed by an
    overloaded human is missed with probability (1 - reliability) — the fatigue-miss (expected).
    """
    n_danger = sum(1 for a in actions if a["gold"] in _DANGER)
    misses = 0.0
    load = 0
    escalated = 0
    for a in actions:
        danger = a["gold"] in _DANGER
        if a["score"] < theta:  # guard auto-allows
            if danger:
                misses += 1.0  # guard miss
        else:  # escalate to the human
            escalated += 1
            load += 1
            if danger:
                misses += 1.0 - reliability(load, capacity)  # fatigue miss (expected)
    n = len(actions)
    return {
        "theta": theta,
        "escalation_rate": round(escalated / n, 4),
        "realized_miss_rate": round(misses / n_danger, 4) if n_danger else 0.0,
        "realized_misses": round(misses, 2),
    }


def sweep(actions: list[dict], capacity: int) -> list[dict]:
    curve = [simulate(actions, t, capacity) for t in THRESHOLDS]
    return sorted(curve, key=lambda p: p["escalation_rate"])


def optimum(curve: list[dict]) -> dict:
    return min(curve, key=lambda p: p["realized_miss_rate"])


def _plot(results: dict, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    colors = {10: "#ef4444", 25: "#f59e0b", 50: "#10b981"}
    for cap, r in results.items():
        xs = [p["escalation_rate"] * 100 for p in r["curve"]]
        ys = [p["realized_miss_rate"] * 100 for p in r["curve"]]
        ax.plot(xs, ys, "-o", ms=3, color=colors.get(cap, "#888"), label=f"capacity={cap}")
        opt = r["optimum"]
        ax.scatter(
            [opt["escalation_rate"] * 100],
            [opt["realized_miss_rate"] * 100],
            color=colors.get(cap, "#888"),
            s=80,
            zorder=5,
            edgecolor="white",
            linewidth=0.6,
        )
    ax.set_xlabel("escalation rate (% of actions sent to the human)")
    ax.set_ylabel("realized danger-through (%)  ↓ = safer")
    ax.set_title("Oversight has a capacity: realized safety is an inverted-U")
    ax.legend(title="reviewer capacity", fontsize=8)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(f"  wrote {out.name}")


def main() -> None:
    if not CALIB.exists():
        print("Run `python -m eval.calibrate` first to generate calibration.json (the scores).")
        return
    actions = json.loads(CALIB.read_text(encoding="utf-8")).get("actions", [])
    if not actions:
        print("calibration.json has no per-action scores — re-run `python -m eval.calibrate`.")
        return

    print("\n" + "=" * 70)
    print("  Simulated inverted-U — endogenous (fatiguing) reviewer  [MODELING, not a study]")
    print("=" * 70)
    results = {}
    for cap in CAPACITIES:
        curve = sweep(actions, cap)
        opt = optimum(curve)
        results[cap] = {"curve": curve, "optimum": opt}
        escalate_all = max(curve, key=lambda p: p["escalation_rate"])
        print(
            f"  capacity={cap:<3}  best @ escalation_rate={opt['escalation_rate']:.0%} "
            f"(danger-through {opt['realized_miss_rate']:.0%})   "
            f"vs escalate-everything {escalate_all['realized_miss_rate']:.0%}"
        )
    print("=" * 70)
    print("  Optimum is BELOW full escalation, and moves with capacity. Modeled fatigue,")
    print("  not measured — a human study (future work) would fit r(load).\n")

    _plot(results, PNG)
    OUT.write_text(json.dumps({str(k): v for k, v in results.items()}, indent=2), encoding="utf-8")
    print(f"  wrote {OUT.name}\n")


if __name__ == "__main__":
    main()
