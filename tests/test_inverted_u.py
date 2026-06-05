"""Inverted-U simulation tests — pure functions, no API key, no saved data needed."""

from __future__ import annotations

from eval import inverted_u


def test_reliability_decays_after_capacity():
    assert inverted_u.reliability(5, capacity=10) == 1.0  # fresh
    assert inverted_u.reliability(10, capacity=10) == 1.0  # at capacity
    assert inverted_u.reliability(20, capacity=10, slope=0.02) == 1.0 - 10 * 0.02  # 0.8
    assert inverted_u.reliability(1000, capacity=10) == 0.2  # floored at r_min


def test_auto_allow_everything_misses_all_danger():
    actions = [{"gold": "BLOCKED", "score": 90}, {"gold": "SAFE", "score": 10}]
    p = inverted_u.simulate(actions, theta=100, capacity=10)  # everything < 100 -> auto-allow
    assert p["escalation_rate"] == 0.0
    assert p["realized_miss_rate"] == 1.0  # the one dangerous action slips through


def test_fatigue_creates_misses_when_escalating_everything():
    # 30 dangerous actions, tiny capacity -> escalating all overloads the human -> misses > 0.
    actions = [{"gold": "BLOCKED", "score": 90} for _ in range(30)]
    p = inverted_u.simulate(actions, theta=0, capacity=5)  # escalate everything
    assert p["escalation_rate"] == 1.0
    assert p["realized_miss_rate"] > 0.0  # late reviews are fatigued -> rubber-stamped


def test_sweep_and_optimum_are_well_formed():
    actions = [{"gold": "BLOCKED", "score": 80}, {"gold": "SAFE", "score": 20}] * 20
    curve = inverted_u.sweep(actions, capacity=5)
    assert curve == sorted(curve, key=lambda p: p["escalation_rate"])
    opt = inverted_u.optimum(curve)
    assert 0.0 <= opt["realized_miss_rate"] <= 1.0
