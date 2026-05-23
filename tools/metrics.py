"""metrics.py — standard performance metrics computed from a trade log + equity curve."""
from __future__ import annotations
import numpy as np
import pandas as pd


def profit_factor(pnls: np.ndarray | list) -> float:
    pnls = np.asarray(pnls, dtype=float)
    gp = pnls[pnls > 0].sum()
    gl = -pnls[pnls < 0].sum()
    if gl <= 0.0:
        return float("inf") if gp > 0 else 0.0
    return float(gp / gl)


def win_rate(pnls: np.ndarray | list) -> float:
    pnls = np.asarray(pnls, dtype=float)
    if len(pnls) == 0:
        return 0.0
    return float((pnls > 0).sum() / len(pnls))


def expectancy(pnls: np.ndarray | list) -> float:
    pnls = np.asarray(pnls, dtype=float)
    return float(pnls.mean()) if len(pnls) else 0.0


def max_drawdown(equity: np.ndarray | list) -> tuple[float, float]:
    """Return (max_dd_absolute, max_dd_percent_of_peak)."""
    eq = np.asarray(equity, dtype=float)
    if len(eq) == 0:
        return 0.0, 0.0
    peak = np.maximum.accumulate(eq)
    dd_abs = (peak - eq).max()
    dd_pct = ((peak - eq) / peak).max() * 100.0
    return float(dd_abs), float(dd_pct)


def sharpe_ratio(returns: np.ndarray | list, periods_per_year: int = 252) -> float:
    r = np.asarray(returns, dtype=float)
    if len(r) < 2 or r.std() == 0:
        return 0.0
    return float((r.mean() / r.std()) * np.sqrt(periods_per_year))


def sortino_ratio(returns: np.ndarray | list, periods_per_year: int = 252) -> float:
    r = np.asarray(returns, dtype=float)
    downside = r[r < 0]
    if len(r) < 2 or len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float((r.mean() / downside.std()) * np.sqrt(periods_per_year))


def summary(trades_pnl: np.ndarray | list, equity: np.ndarray | list,
            initial_balance: float = 10_000.0) -> dict:
    """One-shot summary dict for reports / JSON output."""
    pnls = np.asarray(trades_pnl, dtype=float)
    eq = np.asarray(equity, dtype=float)
    net = float(pnls.sum())
    dd_abs, dd_pct = max_drawdown(eq)
    # equity-bar returns for Sharpe
    rets = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([0.0])
    return {
        "net_profit":    round(net, 2),
        "return_pct":    round(100.0 * net / initial_balance, 2),
        "trades":        int(len(pnls)),
        "win_rate":      round(100.0 * win_rate(pnls), 2),
        "profit_factor": round(profit_factor(pnls), 3),
        "expectancy":    round(expectancy(pnls), 2),
        "max_dd_abs":    round(dd_abs, 2),
        "max_dd_pct":    round(dd_pct, 2),
        "sharpe":        round(sharpe_ratio(rets), 3),
        "sortino":       round(sortino_ratio(rets), 3),
        "final_equity":  round(float(eq[-1]) if len(eq) else initial_balance, 2),
    }
