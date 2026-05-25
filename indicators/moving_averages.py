"""Moving averages — vectorised, no look-ahead.
SMA, WMA, HMA, VWMA, TEMA, DEMA, KAMA, ALMA, McGinley, LinReg.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from .ema import ema


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def wma(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)


def hma(series: pd.Series, period: int) -> pd.Series:
    """Hull MA — fast, smooth."""
    half = max(1, period // 2)
    sqrtp = max(1, int(round(np.sqrt(period))))
    return wma(2 * wma(series, half) - wma(series, period), sqrtp)


def vwma(close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
    pv = close * volume
    return pv.rolling(period).sum() / volume.rolling(period).sum().replace(0, np.nan)


def tema(series: pd.Series, period: int) -> pd.Series:
    """Triple EMA — lag-reduced."""
    e1 = ema(series, period)
    e2 = ema(e1, period)
    e3 = ema(e2, period)
    return 3 * e1 - 3 * e2 + e3


def dema(series: pd.Series, period: int) -> pd.Series:
    """Double EMA."""
    e1 = ema(series, period)
    e2 = ema(e1, period)
    return 2 * e1 - e2


def kama(series: pd.Series, period: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    """Kaufman Adaptive MA — adjusts smoothing by efficiency ratio."""
    change = (series - series.shift(period)).abs()
    volatility = series.diff().abs().rolling(period).sum()
    er = (change / volatility.replace(0, np.nan)).fillna(0)
    sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
    out = series.copy().astype(float)
    for i in range(1, len(series)):
        prev = out.iloc[i - 1] if not np.isnan(out.iloc[i - 1]) else series.iloc[i - 1]
        out.iloc[i] = prev + sc.iloc[i] * (series.iloc[i] - prev)
    return out


def alma(series: pd.Series, period: int = 9, offset: float = 0.85, sigma: float = 6.0) -> pd.Series:
    """Arnaud Legoux MA — gaussian-weighted, low lag."""
    m = offset * (period - 1)
    s = period / sigma
    weights = np.exp(-((np.arange(period) - m) ** 2) / (2 * s * s))
    weights /= weights.sum()
    return series.rolling(period).apply(lambda x: np.dot(x, weights), raw=True)


def mcginley(series: pd.Series, period: int = 14, k: float = 0.6) -> pd.Series:
    """McGinley Dynamic — auto-adjusting MA, less whippy."""
    out = series.copy().astype(float)
    for i in range(1, len(series)):
        prev = out.iloc[i - 1] if not np.isnan(out.iloc[i - 1]) else series.iloc[i - 1]
        ratio = series.iloc[i] / prev if prev != 0 else 1
        out.iloc[i] = prev + (series.iloc[i] - prev) / (k * period * (ratio ** 4))
    return out


def linreg(series: pd.Series, period: int = 14) -> pd.Series:
    """Linear regression — last value of regression line."""
    def _last(x):
        n = len(x); xs = np.arange(n)
        slope = (n * (xs * x).sum() - xs.sum() * x.sum()) / (n * (xs ** 2).sum() - xs.sum() ** 2)
        intercept = (x.sum() - slope * xs.sum()) / n
        return intercept + slope * (n - 1)
    return series.rolling(period).apply(_last, raw=True)
