"""run_validation.py — full CLAUDE.md autonomous workflow.

Usage:
    python run_validation.py [data_csv]  [account_size]  [risk_pct]

Defaults: data/XAUUSD_M5.csv  10000  0.5

Pipeline:
  1. Load + quality check data
  2. Generate 3 candidate strategies (trend / meanrev / breakout) from skills/
  3. For each:    optimise on IS (genetic, small) -> OOS test -> walkforward -> Monte Carlo
  4. Apply acceptance gate (CLAUDE.md thresholds)
  5. Pick winner (highest MC p5 equity) or NO_EDGE
  6. Write HTML report + MQL5 EA (if VALIDATED)
  7. Print one JSON verdict
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from tools.data_loader import load_mt5_csv, quality_check, resample
from tools.time_utils import in_any_session
from tools.metrics import summary
from backtest_engine import BacktestEngine
from skills import TrendStrategy, MeanRevStrategy, BreakoutStrategy
from optimization import GeneticOptimizer, ParamSpec
from validation import walkforward, monte_carlo, regime_split
from report import write_html_report, export_mq5


# ----------------------------------------------------------- candidate matrix
CANDIDATES = [
    {
        "name":   "trend_v1",
        "cls":    TrendStrategy,
        "family": "trend",
        "specs":  [
            ParamSpec("adx_min",     20, 40,  "float"),
            ParamSpec("ema_gap_atr", 0.2, 1.5, "float"),
            ParamSpec("atr_sl_mult", 1.5, 3.0, "float"),
            ParamSpec("atr_tp_mult", 2.0, 5.0, "float"),
        ],
    },
    {
        "name":   "meanrev_v1",
        "cls":    MeanRevStrategy,
        "family": "meanrev",
        "specs":  [
            ParamSpec("rsi_overbought", 65, 80, "float"),
            ParamSpec("rsi_oversold",   20, 35, "float"),
            ParamSpec("stretch_atr",    1.0, 2.5, "float"),
            ParamSpec("atr_sl_mult",    1.0, 2.5, "float"),
        ],
    },
    {
        "name":   "breakout_v1",
        "cls":    BreakoutStrategy,
        "family": "breakout",
        "specs":  [
            ParamSpec("lookback",    10, 40, "int"),
            ParamSpec("adx_min",     20, 40, "float"),
            ParamSpec("atr_sl_mult", 1.0, 2.5, "float"),
            ParamSpec("atr_tp_mult", 1.5, 4.0, "float"),
        ],
    },
]


# ----------------------------------------------------------- helpers
def engine_factory_kwargs():
    return dict(
        initial_balance=10_000.0,
        point_value=1.0,
        point_size=0.01,
        commission_per_lot=7.0,
        slippage_points=10.0,
    )


def acceptance_gate(metrics_oos: dict, wf: dict, mc: dict, regime: dict | None = None,
                    is_metrics: dict | None = None) -> tuple[bool, list[str]]:
    """CLAUDE.md acceptance criteria. Returns (passed, [reasons_if_failed])."""
    reasons = []
    if metrics_oos["profit_factor"] <= 1.10:
        reasons.append(f"OOS PF {metrics_oos['profit_factor']} <= 1.10")
    if wf and wf.get("profitable_windows", 0) < 0.6 * wf.get("n_windows", 1):
        reasons.append(f"WF only {wf['profitable_windows']}/{wf['n_windows']} windows profitable")
    if mc and mc.get("p5_equity", 0) <= 10_000.0:
        reasons.append(f"MC p5 {mc['p5_equity']} <= start ({10_000.0})")
    if metrics_oos["max_dd_pct"] >= 15.0:
        reasons.append(f"OOS DD {metrics_oos['max_dd_pct']}% >= 15%")
    if metrics_oos["trades"] < 100:
        reasons.append(f"OOS trades {metrics_oos['trades']} < 100")
    if is_metrics and is_metrics["net_profit"] > 0 and metrics_oos["net_profit"] > 0:
        ratio = is_metrics["net_profit"] / metrics_oos["net_profit"]
        if ratio > 2.5:
            reasons.append(f"IS/OOS profit ratio {ratio:.2f} > 2.5 (overfit)")
    return len(reasons) == 0, reasons


# -------------------------------------------------------------- pipeline
def evaluate_candidate(cand: dict, df_full: pd.DataFrame, session_mask, log) -> dict:  # type: ignore[name-defined]
    name = cand["name"]
    cls  = cand["cls"]
    specs = cand["specs"]
    log(f"\n=== {name} ===")
    n = len(df_full)
    is_cut = int(n * 0.7)
    is_df, oos_df = df_full.iloc[:is_cut], df_full.iloc[is_cut:]
    is_mask = session_mask.iloc[:is_cut] if session_mask is not None else None
    oos_mask = session_mask.iloc[is_cut:] if session_mask is not None else None
    ekw = engine_factory_kwargs()

    # ---- 1. quick optimise on IS
    def eval_fn(params):
        strat = cls(params=params)
        res = BacktestEngine(df=is_df, strategy=strat, session_mask=is_mask, **ekw).run()
        if len(res.trades) < 20: return -1.0
        m = summary(res.trade_pnls, res.equity, res.initial_balance)
        return m["profit_factor"] * (1 + m["sharpe"] / 10) * max(0.1, 1 - m["max_dd_pct"] / 100)

    log(f"  Optimising on IS ({len(is_df):,} bars, pop=10, gens=8) ...")
    opt = GeneticOptimizer(specs, eval_fn, population=10, generations=8, seed=42)
    out = opt.run()
    best = out["best_params"]
    log(f"  Best IS fitness: {out['best_score']:.3f}  params: { {k: round(v,3) if isinstance(v,float) else v for k,v in best.items()} }")

    # ---- 2. IS metrics with best params
    is_res = BacktestEngine(df=is_df, strategy=cls(params=best), session_mask=is_mask, **ekw).run()
    is_m = summary(is_res.trade_pnls, is_res.equity, is_res.initial_balance)
    log(f"  IS:  profit=${is_m['net_profit']}  pf={is_m['profit_factor']}  dd={is_m['max_dd_pct']}%  trades={is_m['trades']}")

    # ---- 3. OOS test
    oos_res = BacktestEngine(df=oos_df, strategy=cls(params=best), session_mask=oos_mask, **ekw).run()
    oos_m = summary(oos_res.trade_pnls, oos_res.equity, oos_res.initial_balance)
    log(f"  OOS: profit=${oos_m['net_profit']}  pf={oos_m['profit_factor']}  dd={oos_m['max_dd_pct']}%  trades={oos_m['trades']}")

    # ---- 4. walk-forward (5 windows on full data)
    log("  Walk-forward (5 windows) ...")
    def opt_factory(sp, ef):
        return GeneticOptimizer(sp, ef, population=10, generations=6, seed=42)
    wf = walkforward(df_full, cls, opt_factory, specs, n_windows=5, is_ratio=0.7,
                     engine_kwargs={**ekw, "session_mask": session_mask}, base_params=best)
    log(f"  WF: profitable {wf['profitable_windows']}/{wf['n_windows']}  medianPF={wf['median_oos_pf']:.2f}")

    # ---- 5. Monte Carlo on OOS trades
    log("  Monte Carlo (1000 runs) ...")
    mc = monte_carlo(oos_res.trade_pnls, initial_balance=oos_res.initial_balance, n_runs=1000, seed=42)
    log(f"  MC: p5=${mc['p5_equity']}  median=${mc['p50_equity']}  prob_profit={mc['prob_profitable']*100:.1f}%")

    # ---- 6. regime split
    rg = regime_split(oos_df, oos_res.trades)

    # ---- 7. gate
    passed, reasons = acceptance_gate(oos_m, wf, mc, rg, is_m)
    log(f"  {'PASSED' if passed else 'FAILED'}  {('| ' + '; '.join(reasons)) if reasons else ''}")

    return {
        "name": name, "family": cand["family"], "best_params": best,
        "is_metrics": is_m, "oos_metrics": oos_m,
        "wf": {"profitable_windows": wf["profitable_windows"], "n_windows": wf["n_windows"],
               "median_oos_pf": wf["median_oos_pf"], "passed": wf["passed"]},
        "mc": mc, "regime": rg,
        "passed": passed, "reasons": reasons,
        "oos_equity": oos_res.equity.tolist(),
        "oos_trades": oos_res.trades,
        "is_full": is_res, "oos_full": oos_res,
    }


# ----------------------------------------------------------- main
def main(csv_path: str | None = None, account: float = 10_000.0, risk_pct: float = 0.5):
    import pandas as pd  # ensure available in evaluate_candidate scope
    globals()["pd"] = pd

    csv_path = csv_path or str(HERE / "data" / "XAUUSD_M5.csv")
    log_lines: list[str] = []
    def log(msg: str):
        print(msg)
        log_lines.append(msg)

    t0 = time.time()
    log(f"# quant-lab autonomous validation\n# data: {csv_path}")

    # ---- Phase 1: data
    df_m5 = load_mt5_csv(csv_path)
    q = quality_check(df_m5)
    log(f"# data {q['rows']:,} rows  usable={q['usable_pct']}%  range={q['range']}")
    if q["usable_pct"] < 95:
        print(json.dumps({"verdict": "REJECTED_DATA_QUALITY", "data_report": q}, indent=2))
        return

    df_m15 = resample(df_m5, "15min")
    log(f"# resampled to M15: {len(df_m15):,} bars")
    session = in_any_session(df_m15.index, ["asian", "london", "newyork"])

    # ---- Phase 2-4: evaluate candidates
    results = []
    for cand in CANDIDATES:
        try:
            results.append(evaluate_candidate(cand, df_m15, session, log))
        except Exception as e:
            log(f"  ERROR in {cand['name']}: {e}")

    # ---- Phase 5: decision
    survivors = [r for r in results if r["passed"]]
    if not survivors:
        verdict = {
            "verdict": "NO_EDGE",
            "data_report": q,
            "candidates": [
                {"name": r["name"], "passed": False, "reasons": r["reasons"],
                 "oos_pf": r["oos_metrics"]["profit_factor"],
                 "oos_dd": r["oos_metrics"]["max_dd_pct"],
                 "oos_trades": r["oos_metrics"]["trades"],
                 "mc_p5": r["mc"]["p5_equity"]}
                for r in results
            ],
            "winner": None,
            "elapsed_sec": round(time.time() - t0, 1),
        }
        out_dir = HERE / "report"
        # also write a no-edge HTML for each candidate so user can inspect
        for r in results:
            try:
                write_html_report(
                    out_dir / f"rejected_{r['name']}.html",
                    title=f"REJECTED — {r['name']}", symbol="XAUUSD", period="M15",
                    bars=len(df_m15), metrics=r["oos_metrics"], equity=r["oos_equity"],
                    mc=r["mc"], wf=None, regime=r["regime"],
                )
            except Exception as e:
                log(f"  report fail for {r['name']}: {e}")
        print(json.dumps(verdict, indent=2, default=str))
        return verdict

    # winner = highest MC p5
    winner = max(survivors, key=lambda r: r["mc"]["p5_equity"])
    out_dir = HERE / "report"
    html_path = write_html_report(
        out_dir / f"validated_{winner['name']}.html",
        title=f"VALIDATED — {winner['name']}", symbol="XAUUSD", period="M15",
        bars=len(df_m15), metrics=winner["oos_metrics"], equity=winner["oos_equity"],
        mc=winner["mc"], wf=winner["wf"], regime=winner["regime"],
    )
    mq5_path = None
    if winner["family"] == "trend":
        mq5_path = export_mq5(
            out_dir / f"validated_{winner['name']}.mq5",
            name=winner["name"], symbol="XAUUSD", timeframe="M15",
            params=winner["best_params"], family="trend",
        )

    verdict = {
        "verdict": "VALIDATED",
        "data_report": q,
        "candidates": [
            {"name": r["name"], "passed": r["passed"],
             "oos_pf": r["oos_metrics"]["profit_factor"],
             "oos_dd": r["oos_metrics"]["max_dd_pct"],
             "oos_trades": r["oos_metrics"]["trades"],
             "mc_p5": r["mc"]["p5_equity"],
             "reasons": r["reasons"]}
            for r in results
        ],
        "winner": {
            "name": winner["name"], "family": winner["family"],
            "best_params": winner["best_params"],
            "is_metrics": winner["is_metrics"], "oos_metrics": winner["oos_metrics"],
            "wf": winner["wf"], "mc": winner["mc"], "regime": winner["regime"],
        },
        "html_report": html_path,
        "mq5_file":    mq5_path,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    print(json.dumps(verdict, indent=2, default=str))
    return verdict


if __name__ == "__main__":
    csv = sys.argv[1] if len(sys.argv) > 1 else None
    main(csv)
