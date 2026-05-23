"""engine.py — event-driven bar-by-bar backtest simulator.

Design rules:
  * No look-ahead. The strategy sees only bars[:i+1] when deciding for bar i+1's open.
  * Realistic costs: spread, commission, slippage all applied.
  * Position lifecycle: at most one open position, SL/TP checked intrabar.
  * Deterministic given a seed.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Callable
import numpy as np
import pandas as pd


# ---------------------------- public dataclasses --------------------------- #
@dataclass
class Trade:
    entry_idx: int
    exit_idx: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: int                # +1 long, -1 short
    entry_price: float
    exit_price: float
    sl: float
    tp: float
    lots: float
    pnl: float                    # net of costs
    reason: str                   # 'tp' | 'sl' | 'signal' | 'eod' | 'session_end'


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity: np.ndarray            # equity after each closed trade
    equity_index: list[pd.Timestamp]
    initial_balance: float
    final_balance: float
    metrics: dict = field(default_factory=dict)

    @property
    def trade_pnls(self) -> np.ndarray:
        return np.array([t.pnl for t in self.trades], dtype=float)


# ----------------------------- strategy base ------------------------------- #
class Strategy:
    """Subclass and implement on_bar(). May override precompute() to add
    indicator columns once before the main loop (vectorised — fast)."""
    name: str = "base"
    params: dict = {}

    def precompute(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def on_bar(self, i: int, df: pd.DataFrame, position: Optional[Trade]) -> Optional[dict]:
        """Called on the CLOSE of bar i.
        Return one of:
          None                                    — do nothing
          {'action':'open', 'dir': 1|-1, 'sl': p, 'tp': p, 'lots': l}
          {'action':'close', 'reason': '...'}     — close existing position
        Trade is opened at NEXT bar's open (no look-ahead).
        """
        return None


# ------------------------------ the engine -------------------------------- #
class BacktestEngine:
    def __init__(
        self,
        df: pd.DataFrame,
        strategy: Strategy,
        initial_balance: float = 10_000.0,
        point_value: float = 1.0,       # USD profit per 1 point per 1.00 lot
        point_size: float = 0.01,       # price increment per "point" (XAU 2-digit = 0.01)
        commission_per_lot: float = 0.0,
        slippage_points: float = 0.0,
        spread_override_points: Optional[float] = None,   # override CSV spread
        seed: int = 42,
        session_mask: Optional[pd.Series] = None,         # bool series, same index — when False, no new entries
        force_flat_on_session_end: bool = False,
    ):
        self.df_raw = df
        self.strategy = strategy
        self.balance = float(initial_balance)
        self.initial_balance = float(initial_balance)
        self.point_value = float(point_value)
        self.point_size = float(point_size)
        self.commission_per_lot = float(commission_per_lot)
        self.slippage_points = float(slippage_points)
        self.spread_override_points = spread_override_points
        self.rng = np.random.default_rng(seed)
        self.session_mask = session_mask
        self.force_flat_on_session_end = force_flat_on_session_end

    # ---------------------------------------------------------------- cost
    def _spread_price(self, i: int) -> float:
        if self.spread_override_points is not None:
            return self.spread_override_points * self.point_size
        # CSV spread column is in points
        s = float(self.df.iloc[i].get("spread", 0.0))
        return s * self.point_size

    def _apply_slippage(self, base_price: float, direction: int) -> float:
        if self.slippage_points <= 0:
            return base_price
        slip = self.slippage_points * self.point_size
        # adverse slippage: buys fill higher, sells fill lower
        return base_price + direction * slip

    def _pnl(self, direction: int, entry: float, exit_: float, lots: float) -> float:
        """Money P&L for a closed trade, including commission."""
        price_move = (exit_ - entry) * direction
        gross = price_move / self.point_size * self.point_value * lots
        commission = self.commission_per_lot * lots * 2.0   # in + out
        return gross - commission

    # --------------------------------------------------------------- run
    def run(self) -> BacktestResult:
        self.df = self.strategy.precompute(self.df_raw.copy())
        df = self.df
        n = len(df)
        position: Optional[Trade] = None
        trades: list[Trade] = []
        equity_pts: list[float] = [self.balance]
        equity_idx: list[pd.Timestamp] = [df.index[0]]
        op = df["open"].to_numpy()
        hi = df["high"].to_numpy()
        lo = df["low"].to_numpy()
        cl = df["close"].to_numpy()
        idx = df.index

        for i in range(n - 1):
            # ---- intrabar SL/TP check on bar i+1 (the bar AFTER signal bar)
            if position is not None:
                bar_h = hi[i + 1]
                bar_l = lo[i + 1]
                exit_price = None
                reason = None

                if position.direction == 1:
                    if bar_l <= position.sl:
                        exit_price = position.sl; reason = "sl"
                    elif bar_h >= position.tp:
                        exit_price = position.tp; reason = "tp"
                else:
                    if bar_h >= position.sl:
                        exit_price = position.sl; reason = "sl"
                    elif bar_l <= position.tp:
                        exit_price = position.tp; reason = "tp"

                if exit_price is not None:
                    position.exit_idx = i + 1
                    position.exit_time = idx[i + 1]
                    position.exit_price = float(exit_price)
                    position.pnl = self._pnl(position.direction,
                                             position.entry_price,
                                             position.exit_price,
                                             position.lots)
                    position.reason = reason
                    self.balance += position.pnl
                    trades.append(position)
                    equity_pts.append(self.balance)
                    equity_idx.append(idx[i + 1])
                    position = None

            # ---- on-close decision (bar i), action executes at bar i+1 open
            signal = self.strategy.on_bar(i, df, position)

            if signal is None:
                continue

            action = signal.get("action")
            if action == "close" and position is not None:
                price = self._apply_slippage(op[i + 1], -position.direction)
                position.exit_idx = i + 1
                position.exit_time = idx[i + 1]
                position.exit_price = float(price)
                position.pnl = self._pnl(position.direction,
                                         position.entry_price,
                                         position.exit_price,
                                         position.lots)
                position.reason = signal.get("reason", "signal")
                self.balance += position.pnl
                trades.append(position)
                equity_pts.append(self.balance)
                equity_idx.append(idx[i + 1])
                position = None
                continue

            if action == "open" and position is None:
                # session gate (no new entries when False)
                if self.session_mask is not None and not bool(self.session_mask.iloc[i + 1]):
                    continue
                direction = int(signal["dir"])
                spread = self._spread_price(i + 1)
                # buy at ask = open + spread/2 + slippage; sell at bid = open - spread/2 - slippage
                base = op[i + 1] + (spread / 2.0) * direction
                entry = self._apply_slippage(base, direction)
                position = Trade(
                    entry_idx=i + 1,
                    exit_idx=-1,
                    entry_time=idx[i + 1],
                    exit_time=idx[i + 1],
                    direction=direction,
                    entry_price=float(entry),
                    exit_price=float("nan"),
                    sl=float(signal["sl"]),
                    tp=float(signal["tp"]),
                    lots=float(signal["lots"]),
                    pnl=0.0,
                    reason="open",
                )

        # ---- force-flat at end of data
        if position is not None:
            position.exit_idx = n - 1
            position.exit_time = idx[n - 1]
            position.exit_price = float(cl[n - 1])
            position.pnl = self._pnl(position.direction,
                                     position.entry_price,
                                     position.exit_price,
                                     position.lots)
            position.reason = "eod"
            self.balance += position.pnl
            trades.append(position)
            equity_pts.append(self.balance)
            equity_idx.append(idx[n - 1])

        return BacktestResult(
            trades=trades,
            equity=np.array(equity_pts, dtype=float),
            equity_index=equity_idx,
            initial_balance=self.initial_balance,
            final_balance=self.balance,
        )
