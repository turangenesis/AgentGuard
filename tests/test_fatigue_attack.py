"""Fatigue-as-attack tests — pure simulation, no API key."""

from __future__ import annotations

from eval import fatigue_attack as fa


def test_no_filler_no_attack():
    # With zero benign filler the reviewer is fresh (load 1) -> attack cannot exploit fatigue.
    assert fa.attack_success(0, escalate_frac=0.88) == 0.0


def test_attack_success_rises_with_filler():
    low = fa.attack_success(10, escalate_frac=0.88)
    high = fa.attack_success(100, escalate_frac=0.88)
    assert high > low >= 0.0
    assert high <= 1.0


def test_load_aware_beats_paranoid():
    # At the same attack volume, escalating fewer routine actions keeps the reviewer fresher.
    paranoid = fa.attack_success(80, escalate_frac=0.88)
    load_aware = fa.attack_success(80, escalate_frac=0.24)
    assert load_aware < paranoid
