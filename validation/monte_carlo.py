"""monte_carlo.py — bootstrap equity simulation by shuffling trade order.

Tests whether the equity curve is driven by genuine edge or by sequence luck.
Returns confidence intervals on final equity and max drawdown.
"""
from __future__ import annotations
import numpy as np


def monte_carlo(trade_pnls: np.ndarray | list,
                initial_balance: float = 10_000.0,
                n_runs: int = 1000,
                seed: int = 42) -> dict:
    pnls = np.asarray(trade_pnls, dtype=float)
    if len(pnls) == 0:
        return {"n_runs": 0, "p5_equity": initial_balance, "p50_equity": initial_balance,
                "p95_equity": initial_balance, "prob_profitable": 0.0,
                "p5_dd_pct": 0.0, "p50_dd_pct": 0.0, "p95_dd_pct": 0.0, "passed": False}

    rng = np.random.default_rng(seed)
    finals = np.empty(n_runs)
    max_dds = np.empty(n_runs)

    for i in range(n_runs):
        order = rng.permutation(len(pnls))
        eq = initial_balance + np.cumsum(pnls[order])
        eq = np.concatenate([[initial_balance], eq])
        peak = np.maximum.accumulate(eq)
        dd_pct = ((peak - eq) / peak).max() * 100
        finals[i] = eq[-1]
        max_dds[i] = dd_pct

    p5_eq, p50_eq, p95_eq = np.percentile(finals, [5, 50, 95])
    p5_dd, p50_dd, p95_dd = np.percentile(max_dds, [5, 50, 95])
    prob_profit = float((finals > initial_balance).mean())

    return {
        "n_runs":           int(n_runs),
        "p5_equity":        round(float(p5_eq), 2),
        "p50_equity":       round(float(p50_eq), 2),
        "p95_equity":       round(float(p95_eq), 2),
        "p5_dd_pct":        round(float(p5_dd), 2),
        "p50_dd_pct":       round(float(p50_dd), 2),
        "p95_dd_pct":       round(float(p95_dd), 2),
        "prob_profitable":  round(prob_profit, 4),
        "passed":           bool(p5_eq > initial_balance),   # CLAUDE.md gate: MC 5th-pct > start
    }
