"""Indicator library — vectorised, deterministic, no look-ahead.
Each function takes a pandas Series/DataFrame and returns a Series of the same length.
All indicators use only data up to and including the current bar (no shift bug)."""
from .ema import ema
from .rsi import rsi
from .atr import atr, true_range
from .adx import adx
from .vwap import vwap
from .moving_averages import (sma, wma, hma, vwma, tema, dema, kama, alma,
                              mcginley, linreg)
from .oscillators import (macd, stoch, cci, williams_r, awesome_osc,
                          roc, mfi, tsi, ultimate_osc)
from .volatility import bollinger, keltner, donchian, stddev, natr
from .volume import obv, adl, cmf, eom, volume_oscillator
from .trend import supertrend, parabolic_sar, ichimoku, aroon
from .pivots import standard_pivots, camarilla_pivots, woodie_pivots, fib_pivots

__all__ = [
    # base 5
    "ema", "rsi", "atr", "true_range", "adx", "vwap",
    # moving averages (10)
    "sma", "wma", "hma", "vwma", "tema", "dema", "kama", "alma", "mcginley", "linreg",
    # oscillators (9)
    "macd", "stoch", "cci", "williams_r", "awesome_osc", "roc", "mfi", "tsi", "ultimate_osc",
    # volatility (5)
    "bollinger", "keltner", "donchian", "stddev", "natr",
    # volume (5)
    "obv", "adl", "cmf", "eom", "volume_oscillator",
    # trend (4)
    "supertrend", "parabolic_sar", "ichimoku", "aroon",
    # pivots (4)
    "standard_pivots", "camarilla_pivots", "woodie_pivots", "fib_pivots",
]
