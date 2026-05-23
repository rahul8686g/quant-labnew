"""walkforward.py — k-window walk-forward analysis.

Splits the data into K non-overlapping windows. Each window:
  * IS portion (default 70%) → optimise params via the provided optimizer
  * OOS portion (default 30%) → test with those params, record metrics

A strategy is robust if >=60% of OOS windows are profitable AND median OOS PF > 1.0.
"""
from __future__ import annotations
from typing import Callable
import pandas as pd

from backtest_engine import BacktestEngine
from tools.metrics import summary


def walkforward(
    df: pd.DataFrame,
    strategy_cls,
    optimizer_factory: Callable,        # returns an optimizer given (param_specs, eval_fn)
    param_specs: list,
    n_windows: int = 5,
    is_ratio: float = 0.7,
    engine_kwargs: dict | None = None,
    base_params: dict | None = None,
) -> dict:
    engine_kwargs = engine_kwargs or {}
    base_params = base_params or {}
    n = len(df)
    win_size = n // n_windows
    results = []

    for w in range(n_windows):
        start = w * win_size
        end = start + win_size if w < n_windows - 1 else n
        win = df.iloc[start:end]
        if len(win) < 200:
            continue
        cut = int(len(win) * is_ratio)
        is_df = win.iloc[:cut]
        oos_df = win.iloc[cut:]

        # ---- optimise on IS
        def eval_fn(params):
            p = {**base_params, **params}
            strat = strategy_cls(params=p)
            res = BacktestEngine(df=is_df, strategy=strat, **engine_kwargs).run()
            if len(res.trades) < 20:
                return -1.0
            m = summary(res.trade_pnls, res.equity, res.initial_balance)
            # composite fitness: PF * (1 + sharpe/10) * (1 - dd/100)
            return m["profit_factor"] * (1 + m["sharpe"] / 10) * max(0.1, 1 - m["max_dd_pct"] / 100)

        opt = optimizer_factory(param_specs, eval_fn)
        out = opt.run()
        best_params = {**base_params, **out["best_params"]}

        # ---- test on OOS with those params
        strat = strategy_cls(params=best_params)
        res = BacktestEngine(df=oos_df, strategy=strat, **engine_kwargs).run()
        oos_m = summary(res.trade_pnls, res.equity, res.initial_balance) if len(res.trades) else None

        results.append({
            "window": w + 1,
            "is_range": [str(is_df.index[0]), str(is_df.index[-1])],
            "oos_range": [str(oos_df.index[0]), str(oos_df.index[-1])],
            "best_params": best_params,
            "is_fitness": out["best_score"],
            "oos_metrics": oos_m,
        })

    # ---- summary
    profitable = sum(1 for r in results if r["oos_metrics"] and r["oos_metrics"]["net_profit"] > 0)
    pfs = [r["oos_metrics"]["profit_factor"] for r in results if r["oos_metrics"]]
    median_pf = sorted(pfs)[len(pfs) // 2] if pfs else 0.0
    return {
        "windows": results,
        "n_windows": len(results),
        "profitable_windows": profitable,
        "median_oos_pf": median_pf,
        "passed": (profitable >= 0.6 * len(results)) and (median_pf > 1.0) if results else False,
    }
