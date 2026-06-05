"""Noise-floor kappa math tests — dependency-free, no API key (labeling is separate)."""

from __future__ import annotations

from eval import noise_floor


def test_cohens_kappa_perfect_and_inverse():
    assert noise_floor.cohens_kappa(["A", "A", "B", "B"], ["A", "A", "B", "B"]) == 1.0
    # Total disagreement on a balanced 2-class set -> kappa = -1.
    assert noise_floor.cohens_kappa(["A", "B"], ["B", "A"]) == -1.0


def test_cohens_kappa_all_same_category_is_chance():
    # Both raters always say "A": observed agreement is 1 but so is chance -> kappa 1.0 (guard).
    assert noise_floor.cohens_kappa(["A", "A"], ["A", "A"]) == 1.0


def test_fleiss_kappa_perfect_agreement():
    # 2 items, 3 raters, unanimous within each item -> perfect agreement.
    ratings = [["SAFE", "SAFE", "SAFE"], ["BLOCKED", "BLOCKED", "BLOCKED"]]
    assert noise_floor.fleiss_kappa(ratings) == 1.0


def test_fleiss_kappa_total_disagreement_is_low():
    # Maximal spread within each item -> agreement at/below chance.
    ratings = [["SAFE", "APPROVAL_REQUIRED", "BLOCKED"], ["SAFE", "APPROVAL_REQUIRED", "BLOCKED"]]
    assert noise_floor.fleiss_kappa(ratings) <= 0.0


def test_run_with_fake_labelers_is_key_free():
    records = [{"kind": "read", "target": "x", "label": "SAFE"}] * 3
    labelers = [
        ("a", lambda action: "SAFE"),
        ("b", lambda action: "SAFE"),
        ("c", lambda action: "SAFE"),
    ]
    result = noise_floor.run(records, labelers)
    assert result["noise_floor_fleiss_kappa"] == 1.0  # everyone agrees
    assert result["majority_vs_gold_agreement"] == 1.0
