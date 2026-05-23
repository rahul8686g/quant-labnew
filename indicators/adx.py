"""ADX — Average Directional Index. Returns the ADX line.
Matches MetaTrader iADX main buffer."""
from __future__ import annotations
import pandas as pd
from .atr import true_range


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm  = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move.clip(lower=0)
    minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move.clip(lower=0)

    tr = true_range(high, low, close)
    atr_w = tr.ewm(alpha=1.0 / period, adjust=False).mean()

    plus_di  = 100.0 * (plus_dm.ewm(alpha=1.0 / period, adjust=False).mean()  / atr_w.replace(0.0, 1e-12))
    minus_di = 100.0 * (minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_w.replace(0.0, 1e-12))

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, 1e-12)
    return dx.ewm(alpha=1.0 / period, adjust=False).mean()
