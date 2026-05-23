"""pullback_template.py — trend-pullback strategy.

Idea: in an established trend (price above long EMA), wait for a pullback
to the short EMA (RSI cools off), then enter in the trend direction.
Higher win rate than pure trend chasing, similar R:R.
"""
from __future__ import annotations
import pandas as pd

from backtest_engine import Strategy
from indicators import ema, rsi, atr


class PullbackStrategy(Strategy):
    name = "pullback_v1"
    params = {
        "ema_trend":         50,     # the EMA to pull back to
        "ema_long":          200,    # macro trend filter
        "rsi_period":        14,
        "rsi_pullback_max":  55.0,   # for longs: RSI must dip BELOW this on the pullback
        "rsi_pullback_min":  45.0,   # for shorts: RSI must rise ABOVE this on the pullback
        "max_dist_atr":      0.5,    # entry only when price within this * ATR of ema_trend
        "atr_period":        14,
        "atr_sl_mult":       1.5,
        "atr_tp_mult":       3.0,
        "risk_pct":          0.5,
    }

    def __init__(self, params: dict | None = None, point_size: float = 0.01, point_value: float = 1.0):
        if params:
            self.params = {**self.params, **params}
        self.point_size = point_size
        self.point_value = point_value
        self._balance_ref = 10_000.0

    def precompute(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df["ema_t"] = ema(df["close"], p["ema_trend"])
        df["ema_l"] = ema(df["close"], p["ema_long"])
        df["rsi"]   = rsi(df["close"], p["rsi_period"])
        df["atr"]   = atr(df["high"], df["low"], df["close"], p["atr_period"])
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
        if i < max(p["ema_long"], 50):
            return None
        row = df.iloc[i]
        if pd.isna(row["atr"]) or pd.isna(row["ema_l"]):
            return None

        dist = abs(row["close"] - row["ema_t"]) / row["atr"]
        if dist > p["max_dist_atr"]:
            return None  # price too far from short EMA — not a pullback

        # UPTREND pullback long
        if (row["close"] > row["ema_l"] and row["ema_t"] > row["ema_l"]
                and row["rsi"] <= p["rsi_pullback_max"]):
            entry = row["close"]
            sl_dist = p["atr_sl_mult"] * row["atr"]
            sl = entry - sl_dist
            tp = entry + p["atr_tp_mult"] * row["atr"]
            return {"action": "open", "dir": 1, "sl": float(sl), "tp": float(tp), "lots": self._lots(sl_dist)}

        # DOWNTREND pullback short
        if (row["close"] < row["ema_l"] and row["ema_t"] < row["ema_l"]
                and row["rsi"] >= p["rsi_pullback_min"]):
            entry = row["close"]
            sl_dist = p["atr_sl_mult"] * row["atr"]
            sl = entry + sl_dist
            tp = entry - p["atr_tp_mult"] * row["atr"]
            return {"action": "open", "dir": -1, "sl": float(sl), "tp": float(tp), "lots": self._lots(sl_dist)}
        return None
