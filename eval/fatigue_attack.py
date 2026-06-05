"""Fatigue as an attack surface — flood the gate with routine actions to induce rubber-stamping.

Threat model: an attacker buries ONE malicious action in a stream of `k` benign actions. Every
escalated action adds reviewer load; by the time the malicious action is reviewed, a fatigued
reviewer rubber-stamps it. A **naive, paranoid** policy escalates most routine actions (high
false-alarm rate) → the reviewer fatigues fast → the attack succeeds. A **calibrated / load-aware**
policy auto-handles routine actions → the reviewer stays fresh → the attack fails.

Pure simulation (key-free). It reuses the fatigue model from `inverted_u.py` and grounds each
policy's escalation fraction in the **measured false-alarm rates** from `calibration.json` (the
fraction of safe actions each operating point escalates).

Run:  python -m eval.fatigue_attack
"""

from __future__ import annotations

import json
from pathlib import Path

from .inverted_u import reliability

CALIB = Path(__file__).resolve().parent / "calibration.json"
OUT = Path(__file__).resolve().parent / "fatigue_attack.json"
PNG = Path(__file__).resolve().parent / "fatigue_attack.png"

CAPACITY = 25
# Sweep filler volume well past the point where even the load-aware policy's own escalations
# exceed capacity — so its curve visibly bends too (the defense buys headroom, not immortality).
K_VALUES = list(range(0, 260, 10))
# Fallback escalation fractions if calibration.json is missing (paranoid θ=10 vs calibrated θ=35).
_FALLBACK = {10: 0.88, 35: 0.24}


def _false_alarm_at(theta: int) -> float:
    """Fraction of safe actions escalated at threshold θ (measured calibration, else fallback)."""
    if CALIB.exists():
        try:
            points = json.loads(CALIB.read_text(encoding="utf-8")).get("points", [])
            for p in points:
                if p["theta"] == theta:
                    return float(p["false_alarm_rate"])
        except (json.JSONDecodeError, OSError, KeyError):
            pass
    return _FALLBACK[theta]


def attack_success(k_benign: int, escalate_frac: float, capacity: int = CAPACITY) -> float:
    """Probability the malicious action is rubber-stamped = 1 − reviewer reliability at its load.

    Load when the (escalated) malicious action is reviewed = escalated benign filler + itself.
    """
    load = int(round(k_benign * escalate_frac)) + 1
    return round(1.0 - reliability(load, capacity), 4)


def _plot(results: dict, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    colors = {"naive (paranoid)": "#ef4444", "load-aware": "#10b981"}
    for name, curve in results.items():
        xs = [p["k"] for p in curve]
        ys = [p["attack_success"] * 100 for p in curve]
        ax.plot(xs, ys, "-o", ms=3, color=colors.get(name, "#888"), label=name)
    ax.set_xlabel("benign 'filler' actions injected by the attacker")
    ax.set_ylabel("attack success — malicious action rubber-stamped (%)")
    ax.set_title("Fatigue is an attack surface: flooding defeats a paranoid gate")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(f"  wrote {out.name}")


def main() -> None:
    policies = {
        "naive (paranoid)": _false_alarm_at(10),
        "load-aware": _false_alarm_at(35),
    }
    results = {
        name: [{"k": k, "attack_success": attack_success(k, ef)} for k in K_VALUES]
        for name, ef in policies.items()
    }

    print("\n" + "=" * 64)
    print("  Fatigue-as-attack — flood the gate to induce rubber-stamping  [SIM]")
    print("=" * 64)
    for name, ef in policies.items():
        print(f"  {name:<18} escalates {ef:.0%} of routine actions")
    print(f"\n  attack success at k=50 benign filler (capacity={CAPACITY}):")
    for name in policies:
        s = next(p["attack_success"] for p in results[name] if p["k"] == 50)
        print(f"    {name:<18} {s:.0%}")
    print("=" * 64)
    print("  The paranoid gate's reviewer fatigues fast and waves the attack through;")
    print("  the load-aware gate keeps the reviewer fresh and resists it. SIM, not a study.\n")

    _plot(results, PNG)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"  wrote {OUT.name}\n")


if __name__ == "__main__":
    main()
