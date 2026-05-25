"""Trend indicators — SuperTrend, ParabolicSAR, Ichimoku, Aroon."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .atr import atr


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
               period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """SuperTrend — cols: supertrend, direction (+1 up / -1 down)."""
    a = atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper = hl2 + multiplier * a
    lower = hl2 - multiplier * a
    n = len(close)
    st = pd.Series(np.nan, index=close.index)
    dirn = pd.Series(1, index=close.index)
    for i in range(1, n):
        if close.iloc[i] > upper.iloc[i - 1]:
            dirn.iloc[i] = 1
        elif close.iloc[i] < lower.iloc[i - 1]:
            dirn.iloc[i] = -1
        else:
            dirn.iloc[i] = dirn.iloc[i - 1]
            if dirn.iloc[i] == 1 and lower.iloc[i] < lower.iloc[i - 1]:
                lower.iloc[i] = lower.iloc[i - 1]
            elif dirn.iloc[i] == -1 and upper.iloc[i] > upper.iloc[i - 1]:
                upper.iloc[i] = upper.iloc[i - 1]
        st.iloc[i] = lower.iloc[i] if dirn.iloc[i] == 1 else upper.iloc[i]
    return pd.DataFrame({"supertrend": st, "direction": dirn})


def parabolic_sar(high: pd.Series, low: pd.Series, af_start: float = 0.02,
                  af_step: float = 0.02, af_max: float = 0.2) -> pd.Series:
    """Parabolic SAR."""
    n = len(high); sar = np.zeros(n); af = af_start
    long = True; ep = high.iloc[0]; sar[0] = low.iloc[0]
    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if long:
            sar[i] = min(sar[i], low.iloc[i - 1], low.iloc[i - 2] if i >= 2 else low.iloc[i - 1])
            if high.iloc[i] > ep:
                ep = high.iloc[i]; af = min(af + af_step, af_max)
            if low.iloc[i] < sar[i]:
                long = False; sar[i] = ep; ep = low.iloc[i]; af = af_start
        else:
            sar[i] = max(sar[i], high.iloc[i - 1], high.iloc[i - 2] if i >= 2 else high.iloc[i - 1])
            if low.iloc[i] < ep:
                ep = low.iloc[i]; af = min(af + af_step, af_max)
            if high.iloc[i] > sar[i]:
                long = True; sar[i] = ep; ep = high.iloc[i]; af = af_start
    return pd.Series(sar, index=high.index)


def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series,
             tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> pd.DataFrame:
    """Ichimoku Cloud — cols: tenkan, kijun, senkou_a, senkou_b, chikou."""
    t = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    k = (high.rolling(kijun).max()  + low.rolling(kijun).min())  / 2
    sa = ((t + k) / 2).shift(kijun)
    sb = ((high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2).shift(kijun)
    ch = close.shift(-kijun)   # chikou — only useful for visual, NOT for live signals
    return pd.DataFrame({"tenkan": t, "kijun": k, "senkou_a": sa, "senkou_b": sb, "chikou": ch})


def aroon(high: pd.Series, low: pd.Series, period: int = 25) -> pd.DataFrame:
    """Aroon Up/Down/Oscillator."""
    up = high.rolling(period + 1).apply(lambda x: x.argmax() / period * 100, raw=True)
    dn = low.rolling(period + 1).apply(lambda x: x.argmin() / period * 100, raw=True)
    return pd.DataFrame({"up": up, "down": dn, "osc": up - dn})
