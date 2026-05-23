"""trend_template.py — multi-timeframe EMA + RSI + ADX trend-following strategy.

Mirrors the IntradayPro MT5 EA's logic so backtest results are directly comparable.
Bar-close evaluation only — no look-ahead.
"""
from __future__ import annotations
import pandas as pd

from backtest_engine import Strategy
from indicators import ema, rsi, atr, adx


class TrendStrategy(Strategy):
    name = "trend_v1"
    params = {
        # indicator periods
        "ema_fast":         50,
        "ema_slow":         200,
        "rsi_period":       14,
        "atr_period":       14,
        "adx_period":       14,
        # higher-TF lookback (in bars of the current TF)
        "confirm_factor":   4,        # confirm TF = current * 4 (e.g. M15 -> H1)
        "trend_factor":     16,       # trend TF = current * 16 (e.g. M15 -> H4)
        # signal thresholds
        "rsi_buy_above":    52.0,
        "rsi_sell_below":   48.0,
        "adx_min":          35.0,
        "ema_gap_atr":      1.0,      # exec EMAs must be >= this * ATR apart
        # trade management
        "atr_sl_mult":      2.0,
        "atr_tp_mult":      4.0,
        # position sizing
        "risk_pct":         0.5,      # % of account per trade
    }

    def __init__(self, params: dict | None = None, point_size: float = 0.01, point_value: float = 1.0):
        if params:
            self.params = {**self.params, **params}
        self.point_size = point_size
        self.point_value = point_value
        self._balance_ref = 10_000.0   # updated externally if you want compounding sizing

    # ------------------------------------------------------------- precompute
    def precompute(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        # exec-TF indicators
        df["ema_fast"] = ema(df["close"], p["ema_fast"])
        df["ema_slow"] = ema(df["close"], p["ema_slow"])
        df["rsi"]      = rsi(df["close"], p["rsi_period"])
        df["atr"]      = atr(df["high"], df["low"], df["close"], p["atr_period"])
        df["adx"]      = adx(df["high"], df["low"], df["close"], p["adx_period"])

        # higher TFs: take rolling EMAs over confirm_factor / trend_factor bars
        # this is a fast proxy for true multi-TF when the data is already resampled.
        cf, tf = p["confirm_factor"], p["trend_factor"]
        df["ema_fast_c"] = ema(df["close"], p["ema_fast"] * cf)
        df["ema_slow_c"] = ema(df["close"], p["ema_slow"] * cf)
        df["ema_fast_t"] = ema(df["close"], p["ema_fast"] * tf)
        df["ema_slow_t"] = ema(df["close"], p["ema_slow"] * tf)
        return df

    # --------------------------------------------------------------- helpers
    def _lots(self, sl_distance_price: float) -> float:
        """Position size = risk_amount / risk_per_lot. Rounded to 0.01."""
        risk_amount = self._balance_ref * self.params["risk_pct"] / 100.0
        risk_per_lot = (sl_distance_price / self.point_size) * self.point_value
        if risk_per_lot <= 0:
            return 0.01
        lots = risk_amount / risk_per_lot
        # MT5 typical: min 0.01, step 0.01
        lots = max(0.01, round(lots, 2))
        return lots

    # --------------------------------------------------------------- on_bar
    def on_bar(self, i: int, df: pd.DataFrame, position):
        if position is not None:
            return None
        p = self.params

        # need enough warm-up
        if i < max(p["ema_slow"] * p["trend_factor"], 50):
            return None

        # use the LAST CLOSED bar (i) — never i+1 (would be look-ahead)
        row = df.iloc[i]
        if pd.isna(row["atr"]) or pd.isna(row["adx"]) or pd.isna(row["ema_fast_t"]):
            return None

        # 1) trend TF
        trend_dir = 1 if row["ema_fast_t"] > row["ema_slow_t"] else (-1 if row["ema_fast_t"] < row["ema_slow_t"] else 0)
        if trend_dir == 0:
            return None
        # 2) confirm TF must agree
        conf_dir = 1 if row["ema_fast_c"] > row["ema_slow_c"] else (-1 if row["ema_fast_c"] < row["ema_slow_c"] else 0)
        if conf_dir != trend_dir:
            return None
        # 3) execution TF
        exec_dir = 1 if row["ema_fast"] > row["ema_slow"] else (-1 if row["ema_fast"] < row["ema_slow"] else 0)
        if exec_dir != trend_dir:
            return None
        # 4) ADX strength
        if row["adx"] < p["adx_min"]:
            return None
        # 5) EMA separation
        if abs(row["ema_fast"] - row["ema_slow"]) < p["ema_gap_atr"] * row["atr"]:
            return None
        # 6) RSI threshold
        if trend_dir == 1 and row["rsi"] <= p["rsi_buy_above"]:
            return None
        if trend_dir == -1 and row["rsi"] >= p["rsi_sell_below"]:
            return None

        # build SL/TP from ATR
        sl_dist = p["atr_sl_mult"] * row["atr"]
        tp_dist = p["atr_tp_mult"] * row["atr"]
        # entry will be at next bar's open — approximate using close for SL/TP placement
        entry_ref = row["close"]
        sl = entry_ref - trend_dir * sl_dist
        tp = entry_ref + trend_dir * tp_dist
        lots = self._lots(sl_dist)
        return {"action": "open", "dir": trend_dir, "sl": float(sl), "tp": float(tp), "lots": lots}
