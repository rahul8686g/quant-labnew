"""momentum_template.py — momentum strategy.

Idea: trade in the direction of recent price velocity (rate of change),
gated by an EMA trend filter and an RSI strength threshold.
"""
from __future__ import annotations
import pandas as pd

from backtest_engine import Strategy
from indicators import ema, rsi, atr


class MomentumStrategy(Strategy):
    name = "momentum_v1"
    params = {
        "ema_filter":    100,    # only trade in direction of this EMA's slope
        "roc_period":    10,     # bars over which to measure rate of change
        "roc_threshold": 0.5,    # min % move to trigger
        "rsi_period":    14,
        "rsi_strength":  55.0,   # RSI must agree with momentum direction
        "atr_period":    14,
        "atr_sl_mult":   1.8,
        "atr_tp_mult":   3.0,
        "risk_pct":      0.5,
    }

    def __init__(self, params: dict | None = None, point_size: float = 0.01, point_value: float = 1.0):
        if params:
            self.params = {**self.params, **params}
        self.point_size = point_size
        self.point_value = point_value
        self._balance_ref = 10_000.0

    def precompute(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df["ema_f"] = ema(df["close"], p["ema_filter"])
        df["rsi"]   = rsi(df["close"], p["rsi_period"])
        df["atr"]   = atr(df["high"], df["low"], df["close"], p["atr_period"])
        df["roc"]   = (df["close"] / df["close"].shift(p["roc_period"]) - 1.0) * 100.0
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
        if i < max(p["ema_filter"], p["roc_period"], 50):
            return None
        row = df.iloc[i]
        if pd.isna(row["atr"]) or pd.isna(row["roc"]) or pd.isna(row["ema_f"]):
            return None

        # LONG — bullish momentum + above EMA filter + RSI strong
        if row["roc"] >= p["roc_threshold"] and row["close"] > row["ema_f"] and row["rsi"] >= p["rsi_strength"]:
            entry = row["close"]
            sl_dist = p["atr_sl_mult"] * row["atr"]
            sl = entry - sl_dist
            tp = entry + p["atr_tp_mult"] * row["atr"]
            return {"action": "open", "dir": 1, "sl": float(sl), "tp": float(tp), "lots": self._lots(sl_dist)}

        # SHORT — bearish momentum + below EMA filter + RSI weak
        if row["roc"] <= -p["roc_threshold"] and row["close"] < row["ema_f"] and row["rsi"] <= (100.0 - p["rsi_strength"]):
            entry = row["close"]
            sl_dist = p["atr_sl_mult"] * row["atr"]
            sl = entry + sl_dist
            tp = entry - p["atr_tp_mult"] * row["atr"]
            return {"action": "open", "dir": -1, "sl": float(sl), "tp": float(tp), "lots": self._lots(sl_dist)}
        return None
