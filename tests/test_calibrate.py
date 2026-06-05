"""Calibration harness tests — pure curve math + key-free dataset scoring (no API key)."""

from __future__ import annotations

from eval import calibrate
from eval.run_eval import load_dataset


def test_decide_threshold():
    assert calibrate.decide(10, 50) == "allow"  # low risk, below theta -> auto-allow
    assert calibrate.decide(90, 50) == "escalate"  # high risk -> ask a human
    assert calibrate.decide(50, 50) == "escalate"  # boundary is exclusive (risk < theta)


def test_evaluate_known_set():
    scored = [("SAFE", 10), ("SAFE", 20), ("BLOCKED", 90), ("APPROVAL_REQUIRED", 60)]
    points = {p["theta"]: p for p in calibrate.evaluate(scored)}

    # theta=50: both SAFE auto-allowed, both dangerous escalated -> no miss, no false alarm.
    p50 = points[50]
    assert p50["miss_rate"] == 0.0
    assert p50["false_alarm_rate"] == 0.0
    # cost = 0 + 0 + (BLOCKED escalate 1) + (APPROVAL escalate 0) = 1 over 4 rows.
    assert p50["expected_cost"] == 0.25

    # theta=100: everything auto-allowed -> both dangerous actions are missed.
    assert points[100]["miss_rate"] == 1.0


def test_summarize_picks_operating_points():
    scored = [("SAFE", 10), ("SAFE", 20), ("BLOCKED", 90), ("APPROVAL_REQUIRED", 60)]
    summ = calibrate.summarize(calibrate.evaluate(scored))
    # The cheapest operating point gates the danger without false-alarming the safe reads:
    # several thresholds (25..60) tie here, so assert the achieved cost, not a specific theta.
    assert summ["cost_min"]["expected_cost"] == 0.25
    assert summ["cost_min"]["miss_rate"] == 0.0
    # Neyman-Pearson at 0 miss exists and false-alarms nobody here.
    assert summ["np_point"] is not None
    assert summ["np_point"]["miss_rate"] == 0.0
    assert summ["np_point"]["false_alarm_rate"] == 0.0
    assert summ["aurc"] >= 0.0


def test_score_dataset_is_key_free_and_bounded():
    records = load_dataset()
    scored, meta = calibrate.score_dataset(records, scorer=None)  # no LLM scorer
    assert len(scored) == len(records)
    assert meta["n_rule"] > 0  # the rule layer scores the clear cases with no key
    assert all(0 <= s <= 100 for _, s in scored)
