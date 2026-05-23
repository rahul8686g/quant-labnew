"""regime_split.py — split equity by market regime and compute per-regime metrics.

Crude regime detection via a long-window EMA slope:
  uptrend   = slope > +threshold
  downtrend = slope < -threshold
  range     = otherwise
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from tools.metrics import summary


def detect_regime(df: pd.DataFrame, ema_window: int = 200, slope_lookback: int = 50) -> pd.Series:
    e = df["close"].ewm(span=ema_window, adjust=False).mean()
    slope = (e - e.shift(slope_lookback)) / e.shift(slope_lookback) * 100  # pct change
    regime = pd.Series("range", index=df.index)
    regime[slope > 0.5] = "uptrend"
    regime[slope < -0.5] = "downtrend"
    return regime


def regime_split(df: pd.DataFrame, trades) -> dict:
    """Compute per-regime metrics for a list of Trade objects."""
    if len(trades) == 0:
        return {"per_regime": {}, "balanced": False}
    regime = detect_regime(df)

    buckets: dict[str, list] = {"uptrend": [], "downtrend": [], "range": []}
    for t in trades:
        # use entry-time regime
        if t.entry_time in regime.index:
            r = regime.loc[t.entry_time]
        else:
            # find nearest
            try:
                r = regime.asof(t.entry_time)
            except Exception:
                r = "range"
        if r in buckets:
            buckets[r].append(t.pnl)

    per_regime = {}
    profitable_count = 0
    for r, pnls in buckets.items():
        if not pnls:
            per_regime[r] = {"trades": 0, "net": 0.0, "profitable": False}
            continue
        net = float(np.sum(pnls))
        per_regime[r] = {
            "trades": len(pnls),
            "net": round(net, 2),
            "win_rate": round(100 * sum(1 for x in pnls if x > 0) / len(pnls), 2),
            "profitable": net > 0,
        }
        if net > 0:
            profitable_count += 1

    return {
        "per_regime": per_regime,
        "profitable_regimes": profitable_count,
        "balanced": profitable_count >= 2,   # ideally profits in >= 2 of 3 regimes
    }
