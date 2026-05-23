"""Exponential moving average."""
from __future__ import annotations
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """EMA with the standard MT5 smoothing (alpha = 2/(period+1)).
    adjust=False matches MetaTrader's recursive definition."""
    return series.ewm(span=period, adjust=False).mean()
