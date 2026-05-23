"""VWAP — volume-weighted average price, anchored to session start.

Resets every new trading day (server-midnight). No look-ahead.
"""
from __future__ import annotations
import pandas as pd


def vwap(df: pd.DataFrame, anchor: str = "D") -> pd.Series:
    """
    df must contain columns: high, low, close, volume.
    anchor: pandas frequency for VWAP reset ('D' = daily, 'W' = weekly).
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, 1.0)   # avoid div-by-zero
    group = df.index.to_period(anchor)
    cum_pv = (tp * vol).groupby(group).cumsum()
    cum_v  = vol.groupby(group).cumsum()
    return (cum_pv / cum_v).rename("vwap")
