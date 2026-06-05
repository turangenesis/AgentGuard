"""N-seed variance — how stable is the calibration result across LLM sampling?

At temperature=0 the scorer is near-deterministic (the deployed setting). To quantify *sampling
sensitivity* we re-score the set N times at a modest temperature and report mean ± spread of the
AURC. This turns a single-seed demonstration into a result with an error bar.

Needs ANTHROPIC_API_KEY (a few cents — N × the no-rule cases on Haiku).

Run:  python -m eval.nseed
"""

from __future__ import annotations

import json
import os
import statistics
from pathlib import Path

from agentguard.policy.guardian import make_llm_scorer

from .calibrate import evaluate, score_dataset, summarize
from .run_eval import load_dataset

OUT = Path(__file__).resolve().parent / "nseed.json"
N = 3
TEMPERATURE = 0.7  # sampling on, to actually surface variance (temp 0 is near-deterministic)


def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("nseed needs ANTHROPIC_API_KEY (it re-scores the set N times).")
        return
    records = load_dataset()

    print("\n" + "=" * 56)
    print(f"  N-seed variance — {N} runs at temperature {TEMPERATURE}")
    print("=" * 56)
    aurcs, cost_mins = [], []
    for i in range(N):
        actions, _ = score_dataset(records, make_llm_scorer(temperature=TEMPERATURE))
        summ = summarize(evaluate([(a["gold"], a["score"]) for a in actions]))
        aurcs.append(summ["aurc"])
        cm = summ["cost_min"]["expected_cost"]
        cost_mins.append(cm)
        print(f"  seed {i + 1}: AURC={summ['aurc']:.3f}  cost-min={cm:.2f}")

    mean, spread = statistics.mean(aurcs), (statistics.pstdev(aurcs) if N > 1 else 0.0)
    rng = f"{min(aurcs):.3f}-{max(aurcs):.3f}"
    print("-" * 56)
    print(f"  AURC over {N} seeds: mean={mean:.3f} +/- {spread:.3f}  (range {rng})")
    print("=" * 56)
    print("  temp=0 is the deployed (stable) setting; this quantifies sampling sensitivity.\n")

    OUT.write_text(
        json.dumps(
            {
                "n": N,
                "temperature": TEMPERATURE,
                "aurc": aurcs,
                "aurc_mean": round(mean, 4),
                "aurc_std": round(spread, 4),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  wrote {OUT.name}\n")


if __name__ == "__main__":
    main()
