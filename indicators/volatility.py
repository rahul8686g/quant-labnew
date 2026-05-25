"""Volatility indicators — Bollinger, Keltner, Donchian, StdDev, NATR."""
from __future__ import annotations
import pandas as pd
from .ema import ema
from .atr import atr


def bollinger(close: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands — cols: mid, upper, lower, bandwidth, percent_b."""
    mid = close.rolling(period).mean()
    sd = close.rolling(period).std()
    upper = mid + std_mult * sd
    lower = mid - std_mult * sd
    bw = (upper - lower) / mid
    pb = (close - lower) / (upper - lower)
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower,
                          "bandwidth": bw, "percent_b": pb})


def keltner(high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = 20, atr_mult: float = 2.0) -> pd.DataFrame:
    """Keltner Channels — EMA mid + ATR bands."""
    mid = ema(close, period)
    a = atr(high, low, close, period)
    return pd.DataFrame({"mid": mid, "upper": mid + atr_mult * a,
                          "lower": mid - atr_mult * a})


def donchian(high: pd.Series, low: pd.Series, period: int = 20) -> pd.DataFrame:
    """Donchian Channels — N-bar high/low."""
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    mid = (upper + lower) / 2
    return pd.DataFrame({"upper": upper, "lower": lower, "mid": mid})


def stddev(series: pd.Series, period: int = 20) -> pd.Series:
    return series.rolling(period).std()


def natr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Normalized ATR — ATR as % of price."""
    return 100 * atr(high, low, close, period) / close
