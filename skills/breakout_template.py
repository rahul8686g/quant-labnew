"""breakout_template.py — Donchian-style breakout with ATR-based SL/TP.

Idea: enter long on break of N-bar high, short on break of N-bar low.
ADX must confirm momentum to avoid false breakouts.
"""
from __future__ import annotations
import pandas as pd

from backtest_engine import Strategy
from indicators import atr, adx


class BreakoutStrategy(Strategy):
    name = "breakout_v1"
    params = {
        "lookback":       20,
        "atr_period":     14,
        "adx_period":     14,
        "adx_min":        25.0,
        "atr_sl_mult":    1.5,
        "atr_tp_mult":    3.0,
        "risk_pct":       0.5,
    }

    def __init__(self, params: dict | None = None, point_size: float = 0.01, point_value: float = 1.0):
        if params:
            self.params = {**self.params, **params}
        self.point_size = point_size
        self.point_value = point_value
        self._balance_ref = 10_000.0

    def precompute(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df["hh"]  = df["high"].rolling(p["lookback"]).max().shift(1)   # shift to avoid look-ahead
        df["ll"]  = df["low"].rolling(p["lookback"]).min().shift(1)
        df["atr"] = atr(df["high"], df["low"], df["close"], p["atr_period"])
        df["adx"] = adx(df["high"], df["low"], df["close"], p["adx_period"])
        return df

    def _lots(self, sl_distance_price: float) -> float:
        risk_amount = self._balance_ref * self.params["risk_pct"] / 100.0
        risk_per_lot = (sl_distance_price / self.point_size) * self.point_value
        if risk_per_lot <= 0:
            return 0.01
        return max(0.01, round(risk_amount / risk_per_lot, 2))

    def on_bar(self, i: int, df: pd.DataFrame, position):
        if position is not None:
            return None
        p = self.params
        if i < max(p["lookback"], p["atr_period"], p["adx_period"]):
            return None
        row = df.iloc[i]
        if pd.isna(row["atr"]) or pd.isna(row["adx"]) or pd.isna(row["hh"]):
            return None
        if row["adx"] < p["adx_min"]:
            return None

        if row["close"] > row["hh"]:
            entry = row["close"]
            sl = entry - p["atr_sl_mult"] * row["atr"]
            tp = entry + p["atr_tp_mult"] * row["atr"]
            return {"action": "open", "dir": 1, "sl": float(sl), "tp": float(tp),
                    "lots": self._lots(entry - sl)}

        if row["close"] < row["ll"]:
            entry = row["close"]
            sl = entry + p["atr_sl_mult"] * row["atr"]
            tp = entry - p["atr_tp_mult"] * row["atr"]
            return {"action": "open", "dir": -1, "sl": float(sl), "tp": float(tp),
                    "lots": self._lots(sl - entry)}
        return None
