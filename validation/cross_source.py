"""cross_source.py — verify a validated winner on a SECOND independent data source.

This catches the most common failure mode: strategy passes backtest on
broker A's data, but loses on broker B (different spread, volatility,
session boundaries). Before this check, "VALIDATED" was a brittle promise.
After this check, a winner is only trusted if it survives 2 sources.

Verdict mapping:
  primary PASS + cross-source PASS         -> VALIDATED_ROBUST
  primary PASS + cross-source FAIL         -> VALIDATED_SINGLE_SOURCE (warning)
  primary PASS + cross-source unavailable  -> VALIDATED_NO_CROSSCHECK
"""
from __future__ import annotations
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from tools.data_loader import fetch_yahoo, resample
from tools.metrics import summary
from backtest_engine import BacktestEngine


# Yahoo intervals corresponding to MT5/Pine timeframe strings
_TF_TO_YAHOO = {
    "5min":  "5m",   "M5":  "5m",
    "15min": "15m",  "M15": "15m",
    "30min": "30m",  "M30": "30m",
    "1H":    "1h",   "H1":  "1h",
    "4H":    "1h",   "H4":  "1h",     # Yahoo has no 4h — use 1h then resample
}

_TF_RESAMPLE = {
    "M15": "15min", "M30": "30min", "H1": "1H", "H4": "4H",
    "15min": "15min", "30min": "30min", "1H": "1H", "4H": "4H",
}


def _strategy_from_family(family: str, params: dict):
    """Build a Strategy instance from a family name + params dict."""
    from skills import (TrendStrategy, MeanRevStrategy, BreakoutStrategy,
                        MomentumStrategy, PullbackStrategy)
    table = {
        "trend":    TrendStrategy,
        "meanrev":  MeanRevStrategy,
        "breakout": BreakoutStrategy,
        "momentum": MomentumStrategy,
        "pullback": PullbackStrategy,
    }
    cls = table.get(family)
    if cls is None:
        raise ValueError(f"unknown family '{family}'")
    return cls(params=params)


def cross_validate_winner(
    family: str,
    params: dict,
    yahoo_symbol: str,
    timeframe: str = "M15",
    initial_balance: float = 10_000.0,
    point_value: float = 1.0,
    point_size: float = 0.01,
    commission_per_lot: float = 7.0,
    slippage_points: float = 10.0,
) -> dict:
    """Re-run the winning strategy on Yahoo Finance data for the same symbol.

    Returns a dict with: available, passed, source, metrics (or error).
    """
    yahoo_interval = _TF_TO_YAHOO.get(timeframe, "30m")
    try:
        df = fetch_yahoo(yahoo_symbol, interval=yahoo_interval, cache=False)
    except Exception as e:
        return {
            "available": False, "passed": False,
            "source": f"yahoo:{yahoo_symbol}", "interval": yahoo_interval,
            "error": str(e),
        }

    if len(df) < 200:
        return {
            "available": False, "passed": False,
            "source": f"yahoo:{yahoo_symbol}", "interval": yahoo_interval,
            "error": f"only {len(df)} bars — too few for meaningful cross-check",
        }

    # Resample if needed (e.g. H4 from 1h)
    target_rule = _TF_RESAMPLE.get(timeframe, timeframe)
    if target_rule != yahoo_interval.replace("m", "min").replace("h", "H"):
        try:
            df = resample(df, target_rule)
        except Exception:
            pass   # if resample fails just use as-is

    strat = _strategy_from_family(family, params)
    res = BacktestEngine(
        df=df, strategy=strat,
        initial_balance=initial_balance,
        point_value=point_value, point_size=point_size,
        commission_per_lot=commission_per_lot,
        slippage_points=slippage_points,
    ).run()
    m = summary(res.trade_pnls, res.equity, res.initial_balance,
                bar_equity=res.bar_equity, bar_equity_index=res.bar_equity_index)

    # Relaxed cross-check gates (less data, just confirm no blow-up):
    #   PF > 1.0      — strategy at least breaks even on second source
    #   profit > 0    — not losing money
    #   DD < 20%      — no catastrophic drawdown
    passed = (m["profit_factor"] > 1.0
              and m["net_profit"] > 0
              and m["max_dd_pct"] < 20.0
              and m["trades"] >= 20)

    return {
        "available": True, "passed": passed,
        "source": f"yahoo:{yahoo_symbol}", "interval": yahoo_interval,
        "bars": len(df), "metrics": m,
        "gate_used": "PF>1.0 AND profit>0 AND DD<20% AND trades>=20 (relaxed for shorter data)",
    }


def adjust_verdict(primary_verdict: dict, cross: dict) -> dict:
    """Given the primary VALIDATED verdict + cross-source result,
    produce a final verdict with appropriate label and warnings."""
    if not cross.get("available"):
        primary_verdict["final_verdict"] = "VALIDATED_NO_CROSSCHECK"
        primary_verdict["warning"] = (
            f"Cross-source check unavailable ({cross.get('error', 'unknown')}). "
            "Demo-forward-test on your live broker is MANDATORY before risking capital.")
    elif cross.get("passed"):
        primary_verdict["final_verdict"] = "VALIDATED_ROBUST"
        primary_verdict["note"] = (
            f"Strategy passed on BOTH primary data and {cross['source']} ({cross['bars']} bars). "
            "Robust to data-source variation.")
    else:
        primary_verdict["final_verdict"] = "VALIDATED_SINGLE_SOURCE"
        m = cross.get("metrics", {})
        primary_verdict["warning"] = (
            f"Strategy passed on primary data but FAILED on {cross['source']} "
            f"(PF={m.get('profit_factor')}, profit=${m.get('net_profit')}, "
            f"DD={m.get('max_dd_pct')}%). HIGH RISK of data-source overfit. "
            "Do NOT trade live without 4-6 weeks demo-forward-test on YOUR broker.")
    primary_verdict["cross_source"] = cross
    return primary_verdict
