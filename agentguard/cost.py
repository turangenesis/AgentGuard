"""Turn per-run token counts into a dollar estimate for the dashboard.

These are **list-price estimates**, not billed truth — the Anthropic console is the
source of truth. Rates are USD per 1M tokens; prompt-cache reads bill at 0.1x input
and the first cache write at 1.25x input. Kept as plain constants so they're easy to
update when prices change.
"""

from __future__ import annotations

# USD per 1,000,000 tokens.
PRICES = {
    "worker": {"in": 3.0, "out": 15.0},  # worker model (Sonnet tier)
    "judge": {"in": 1.0, "out": 5.0},  # guardian judge (Haiku tier)
}
CACHE_READ_MULT = 0.1
CACHE_WRITE_MULT = 1.25


def estimate_run_cost(row: dict) -> dict:
    """Given a run_cost row, return a $ estimate + token totals (all best-effort)."""
    w, j = PRICES["worker"], PRICES["judge"]
    worker_in = row.get("worker_in", 0) or 0
    worker_out = row.get("worker_out", 0) or 0
    judge_in = row.get("judge_in", 0) or 0
    judge_out = row.get("judge_out", 0) or 0
    cache_read = row.get("cache_read", 0) or 0
    cache_create = row.get("cache_create", 0) or 0

    worker_usd = worker_in / 1e6 * w["in"] + worker_out / 1e6 * w["out"]
    judge_usd = (
        judge_in / 1e6 * j["in"]
        + cache_read / 1e6 * j["in"] * CACHE_READ_MULT
        + cache_create / 1e6 * j["in"] * CACHE_WRITE_MULT
        + judge_out / 1e6 * j["out"]
    )
    total_tokens = worker_in + worker_out + judge_in + judge_out + cache_read + cache_create
    return {
        "usd_estimate": round(worker_usd + judge_usd, 4),
        "worker_usd": round(worker_usd, 4),
        "judge_usd": round(judge_usd, 4),
        "total_tokens": total_tokens,
        "cache_read_tokens": cache_read,
    }
