"""Two-model comparison — does a better scoring model give a better-calibrated guard?

Runs the calibration with two judge/scorer models (Haiku vs Sonnet) and overlays their
safety/utility curves. Turns "would a better model be more reliable?" into a *shown* result
instead of a guess — and demonstrates that the finding is **model-dependent** (the framework
measures it; it doesn't pronounce "guards are bad").

Needs ANTHROPIC_API_KEY (a few cents — scores the no-rule cases with each model). Scores at
temperature=0; this is a **single-seed demonstration** — a published claim should run N seeds
and report mean ± spread.

Run:  python -m eval.compare_models
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from headroom.policy.guardian import make_llm_scorer

from .calibrate import evaluate, score_dataset, summarize
from .run_eval import load_dataset

OUT = Path(__file__).resolve().parent / "model_comparison.json"
PNG = Path(__file__).resolve().parent / "model_comparison.png"

MODELS = [
    ("Haiku", "claude-haiku-4-5-20251001", "#10b981"),
    ("Sonnet", "claude-sonnet-4-6", "#6366f1"),
]


def run_model(records: list[dict], model: str) -> dict:
    actions, meta = score_dataset(records, make_llm_scorer(model=model))
    scored = [(a["gold"], a["score"]) for a in actions]
    points = evaluate(scored)
    return {"points": points, "n_llm": meta["n_llm"], **summarize(points)}


def _plot(results: dict, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    for name, color in [(n, c) for n, _, c in MODELS]:
        r = results[name]
        fa = [p["false_alarm_rate"] * 100 for p in r["points"]]
        miss = [p["miss_rate"] * 100 for p in r["points"]]
        ax.plot(fa, miss, "-o", ms=3, color=color, label=f"{name}  (AURC {r['aurc']:.3f})")
    ax.set_xlabel("false-alarm rate (%)")
    ax.set_ylabel("missed-danger rate (%)")
    ax.set_title("Calibration curve by scoring model — 125 hard cases (1 seed, temp 0)")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(f"  wrote {out.name}")


def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("compare_models needs ANTHROPIC_API_KEY (it scores the set with each model).")
        return
    records = load_dataset()
    results = {name: run_model(records, model) for name, model, _ in MODELS}

    print("\n" + "=" * 60)
    print("  Two-model comparison — calibration by scoring model")
    print("=" * 60)
    for name, _, _ in MODELS:
        r = results[name]
        cm = r["cost_min"]
        print(
            f"  {name:<7} AURC={r['aurc']:.3f}  cost-min θ={cm['theta']:<3} "
            f"exp-cost={cm['expected_cost']:.2f}  (llm-scored {r['n_llm']})"
        )
    print("=" * 60)
    print("  Model-dependent — the framework measures it; never claim 'guards are bad'.")
    print("  Single seed, temp 0; a published claim runs N seeds + reports mean ± spread.\n")

    _plot(results, PNG)
    OUT.write_text(
        json.dumps(
            {
                n: {"aurc": r["aurc"], "cost_min": r["cost_min"], "np_point": r["np_point"]}
                for n, r in results.items()
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  wrote {OUT.name}\n")


if __name__ == "__main__":
    main()
