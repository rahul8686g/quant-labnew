"""Oscillators — MACD, Stoch, CCI, Williams%R, AwesomeOsc, ROC, MFI, TSI, RVI, UO.
All vectorised, no look-ahead.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from .ema import ema
from .moving_averages import sma


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Returns DataFrame with cols: macd, signal, hist."""
    m = ema(close, fast) - ema(close, slow)
    s = ema(m, signal)
    return pd.DataFrame({"macd": m, "signal": s, "hist": m - s})


def stoch(high: pd.Series, low: pd.Series, close: pd.Series,
          k_period: int = 14, d_period: int = 3, smooth: int = 3) -> pd.DataFrame:
    """Returns DataFrame with cols: k, d."""
    ll = low.rolling(k_period).min()
    hh = high.rolling(k_period).max()
    raw = 100 * (close - ll) / (hh - ll).replace(0, np.nan)
    k = raw.rolling(smooth).mean()
    d = k.rolling(d_period).mean()
    return pd.DataFrame({"k": k, "d": d})


def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    hh = high.rolling(period).max()
    ll = low.rolling(period).min()
    return -100 * (hh - close) / (hh - ll).replace(0, np.nan)


def awesome_osc(high: pd.Series, low: pd.Series) -> pd.Series:
    """Awesome Oscillator — Bill Williams."""
    median = (high + low) / 2
    return median.rolling(5).mean() - median.rolling(34).mean()


def roc(close: pd.Series, period: int = 10) -> pd.Series:
    """Rate of change in %."""
    return (close / close.shift(period) - 1) * 100


def mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14) -> pd.Series:
    """Money Flow Index — volume-weighted RSI."""
    tp = (high + low + close) / 3
    mf = tp * volume
    pos = mf.where(tp > tp.shift(1), 0.0).rolling(period).sum()
    neg = mf.where(tp < tp.shift(1), 0.0).rolling(period).sum()
    ratio = pos / neg.replace(0, np.nan)
    return 100 - (100 / (1 + ratio))


def tsi(close: pd.Series, long: int = 25, short: int = 13) -> pd.Series:
    """True Strength Index."""
    diff = close.diff()
    abs_diff = diff.abs()
    num = ema(ema(diff, long), short)
    den = ema(ema(abs_diff, long), short).replace(0, np.nan)
    return 100 * num / den


def ultimate_osc(high: pd.Series, low: pd.Series, close: pd.Series,
                 short: int = 7, mid: int = 14, long: int = 28) -> pd.Series:
    """Ultimate Oscillator — weighted multi-period."""
    prev = close.shift(1)
    bp = close - pd.concat([low, prev], axis=1).min(axis=1)
    tr = pd.concat([high, prev], axis=1).max(axis=1) - pd.concat([low, prev], axis=1).min(axis=1)
    avg_s = bp.rolling(short).sum() / tr.rolling(short).sum().replace(0, np.nan)
    avg_m = bp.rolling(mid).sum()   / tr.rolling(mid).sum().replace(0, np.nan)
    avg_l = bp.rolling(long).sum()  / tr.rolling(long).sum().replace(0, np.nan)
    return 100 * (4 * avg_s + 2 * avg_m + avg_l) / 7
