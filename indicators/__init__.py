"""Indicator library — vectorised, deterministic, no look-ahead.
Each function takes a pandas Series/DataFrame and returns a Series of the same length.
All indicators use only data up to and including the current bar (no shift bug)."""
from .ema import ema
from .rsi import rsi
from .atr import atr
from .adx import adx
from .vwap import vwap

__all__ = ["ema", "rsi", "atr", "adx", "vwap"]
