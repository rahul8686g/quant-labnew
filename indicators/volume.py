"""Volume indicators — OBV, ADL, CMF, EOM, Volume Oscillator."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .ema import ema


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On Balance Volume."""
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def adl(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """Accumulation/Distribution Line."""
    rng = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / rng
    return (mfm.fillna(0) * volume).cumsum()


def cmf(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
    """Chaikin Money Flow — period-normalised ADL."""
    rng = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / rng
    mfv = mfm.fillna(0) * volume
    return mfv.rolling(period).sum() / volume.rolling(period).sum().replace(0, np.nan)


def eom(high: pd.Series, low: pd.Series, volume: pd.Series, period: int = 14, scale: float = 1e6) -> pd.Series:
    """Ease of Movement."""
    mid = (high + low) / 2
    move = mid - mid.shift(1)
    box = (volume / scale) / (high - low).replace(0, np.nan)
    return (move / box).rolling(period).mean()


def volume_oscillator(volume: pd.Series, short: int = 5, long: int = 20) -> pd.Series:
    """% diff between short and long EMA of volume."""
    s = ema(volume, short)
    l = ema(volume, long)
    return 100 * (s - l) / l.replace(0, np.nan)
