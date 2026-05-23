"""meanrev_template.py — mean-reversion strategy.

Idea: when price is far stretched from a mid-line (EMA) AND RSI is at an extreme,
fade the move. Exit at the mid-line or via ATR stop.
"""
from __future__ import annotations
import pandas as pd

from backtest_engine import Strategy
from indicators import ema, rsi, atr


class MeanRevStrategy(Strategy):
    name = "meanrev_v1"
    params = {
        "ema_mid":         50,
        "rsi_period":      14,
        "atr_period":      14,
        "rsi_overbought":  72.0,
        "rsi_oversold":    28.0,
        "stretch_atr":     1.5,    # price must be >= this * ATR away from EMA
        "atr_sl_mult":     1.5,
        "atr_tp_mult":     1.5,
        "risk_pct":        0.5,
    }

    def __init__(self, params: dict | None = None, point_size: float = 0.01, point_value: float = 1.0):
        if params:
            self.params = {**self.params, **params}
        self.point_size = point_size
        self.point_value = point_value
        self._balance_ref = 10_000.0

    def precompute(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df["mid"] = ema(df["close"], p["ema_mid"])
        df["rsi"] = rsi(df["close"], p["rsi_period"])
        df["atr"] = atr(df["high"], df["low"], df["close"], p["atr_period"])
        df["stretch"] = (df["close"] - df["mid"]) / df["atr"]
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
        if i < max(p["ema_mid"], 50):
            return None
        row = df.iloc[i]
        if pd.isna(row["atr"]) or pd.isna(row["rsi"]):
            return None

        # SHORT: stretched up + RSI overbought
        if row["stretch"] >= p["stretch_atr"] and row["rsi"] >= p["rsi_overbought"]:
            entry = row["close"]
            sl = entry + p["atr_sl_mult"] * row["atr"]
            tp = entry - p["atr_tp_mult"] * row["atr"]
            return {"action": "open", "dir": -1, "sl": float(sl), "tp": float(tp),
                    "lots": self._lots(sl - entry)}

        # LONG: stretched down + RSI oversold
        if row["stretch"] <= -p["stretch_atr"] and row["rsi"] <= p["rsi_oversold"]:
            entry = row["close"]
            sl = entry - p["atr_sl_mult"] * row["atr"]
            tp = entry + p["atr_tp_mult"] * row["atr"]
            return {"action": "open", "dir": 1, "sl": float(sl), "tp": float(tp),
                    "lots": self._lots(entry - sl)}
        return None
