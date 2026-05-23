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

import pandas as pd

from tools.data_loader import load_mt5_csv, quality_check, resample, fetch_yahoo
from tools.time_utils import in_any_session
from tools.metrics import summary
from backtest_engine import BacktestEngine
from skills import (TrendStrategy, MeanRevStrategy, BreakoutStrategy,
                    MomentumStrategy, PullbackStrategy)
from optimization import GeneticOptimizer, ParamSpec
from validation import walkforward, monte_carlo, regime_split
from report import write_html_report, export_mq5, export_pine, html_to_pdf


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
    {
        "name":   "momentum_v1",
        "cls":    MomentumStrategy,
        "family": "momentum",
        "specs":  [
            ParamSpec("roc_period",    5, 20, "int"),
            ParamSpec("roc_threshold", 0.2, 1.5, "float"),
            ParamSpec("rsi_strength",  50, 65, "float"),
            ParamSpec("atr_sl_mult",   1.2, 2.5, "float"),
        ],
    },
    {
        "name":   "pullback_v1",
        "cls":    PullbackStrategy,
        "family": "pullback",
        "specs":  [
            ParamSpec("rsi_pullback_max", 45, 60, "float"),
            ParamSpec("rsi_pullback_min", 40, 55, "float"),
            ParamSpec("max_dist_atr",     0.2, 1.0, "float"),
            ParamSpec("atr_sl_mult",      1.0, 2.5, "float"),
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
    # ---- overfit guards (two-level) ----
    if is_metrics:
        is_p  = is_metrics.get("net_profit", 0.0)
        oos_p = metrics_oos.get("net_profit", 0.0)
        # (a) Classic overfit: IS makes money, OOS loses money.
        #     Hard fail regardless of other gates. The ratio check below
        #     only fires when both are profitable, so this branch is required.
        if is_p > 0 and oos_p <= 0:
            reasons.append(
                f"OVERFIT: IS profitable (+${is_p:.2f}) but OOS losing (${oos_p:.2f})")
        # (b) Soft overfit: both profitable but IS dwarfs OOS.
        elif is_p > 0 and oos_p > 0:
            ratio = is_p / oos_p
            if ratio > 2.5:
                reasons.append(f"IS/OOS profit ratio {ratio:.2f} > 2.5 (overfit)")
    return len(reasons) == 0, reasons


# -------------------------------------------------------------- pipeline
def evaluate_candidate(cand: dict, df_full: pd.DataFrame, session_mask, log) -> dict:
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

    log(f"  Optimising on IS ({len(is_df):,} bars, pop=20, gens=15) ...")
    opt = GeneticOptimizer(specs, eval_fn, population=20, generations=15, seed=42)
    out = opt.run()
    best = out["best_params"]
    log(f"  Best IS fitness: {out['best_score']:.3f}  params: { {k: round(v,3) if isinstance(v,float) else v for k,v in best.items()} }")

    # ---- 2. IS metrics with best params (bar-equity for accurate DD + daily Sharpe)
    is_res = BacktestEngine(df=is_df, strategy=cls(params=best), session_mask=is_mask, **ekw).run()
    is_m = summary(is_res.trade_pnls, is_res.equity, is_res.initial_balance,
                   bar_equity=is_res.bar_equity, bar_equity_index=is_res.bar_equity_index)
    log(f"  IS:  profit=${is_m['net_profit']}  pf={is_m['profit_factor']}  dd={is_m['max_dd_pct']}%  trades={is_m['trades']}")

    # ---- 3. OOS test (bar-equity for accurate DD + daily Sharpe)
    oos_res = BacktestEngine(df=oos_df, strategy=cls(params=best), session_mask=oos_mask, **ekw).run()
    oos_m = summary(oos_res.trade_pnls, oos_res.equity, oos_res.initial_balance,
                    bar_equity=oos_res.bar_equity, bar_equity_index=oos_res.bar_equity_index)
    log(f"  OOS: profit=${oos_m['net_profit']}  pf={oos_m['profit_factor']}  dd={oos_m['max_dd_pct']}%  trades={oos_m['trades']}")

    # ---- 4. walk-forward (5 windows on full data)
    log("  Walk-forward (5 windows) ...")
    def opt_factory(sp, ef):
        return GeneticOptimizer(sp, ef, population=12, generations=8, seed=42)
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
    """Run the full validation pipeline. Prints ONLY the final JSON to stdout.
    All progress logs go to report/run.log per CLAUDE.md output rules."""
    csv_path = csv_path or str(HERE / "data" / "XAUUSD_M5.csv")
    # Per-run output folder so reports never overwrite each other.
    # Name: report/run_YYYYMMDD-HHMMSS_<symbol-guess>/
    run_stamp = time.strftime("%Y%m%d-%H%M%S")
    symbol_tag = Path(csv_path).stem.split("_")[0].upper() or "RUN"
    run_dir = HERE / "report" / f"run_{run_stamp}_{symbol_tag}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []
    log_path = run_dir / "run.log"

    def log(msg: str):
        # silent — do NOT print to stdout; CLAUDE.md says JSON only on stdout.
        log_lines.append(msg)

    t0 = time.time()
    log(f"# quant-lab autonomous validation\n# data: {csv_path}")

    # ---- Phase 1: data — try local CSV first, else fall back to Yahoo Finance
    src = Path(csv_path)
    data_source = "local_csv"
    if src.is_file():
        df_m5 = load_mt5_csv(src)
    else:
        log(f"# CSV not found at {csv_path} — fetching from Yahoo Finance")
        # treat the path basename (or the whole arg) as a Yahoo symbol
        symbol_guess = src.stem.split("_")[0] if "_" in src.stem else (src.stem or csv_path)
        try:
            df_m5 = fetch_yahoo(symbol_guess, interval="5m")
            data_source = f"yahoo:{symbol_guess}"
            log(f"# fetched {len(df_m5):,} bars from Yahoo for '{symbol_guess}'")
        except Exception as e:
            log_path.write_text("\n".join(log_lines), encoding="utf-8")
            print(json.dumps({
                "verdict": "REJECTED_NO_DATA",
                "csv_path": csv_path,
                "yahoo_attempt": symbol_guess,
                "error": str(e),
            }, indent=2))
            return
    q = quality_check(df_m5)
    q["source"] = data_source
    log(f"# data {q['rows']:,} rows  usable={q['usable_pct']}%  range={q['range']}")
    if q["usable_pct"] < 95:
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
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
        out_dir = run_dir
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
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
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
    # PDF (best-effort — Edge/Chrome headless)
    pdf_path = html_to_pdf(html_path, out_dir / f"validated_{winner['name']}.pdf")
    pdf_status = "ok" if pdf_path else "no_browser_found"
    # Always try to export both MT5 (.mq5) and TradingView (.pine)
    mq5_path, mq5_status = None, "ok"
    try:
        mq5_path = export_mq5(
            out_dir / f"validated_{winner['name']}.mq5",
            name=winner["name"], symbol="XAUUSD", timeframe="M15",
            params=winner["best_params"], family=winner["family"],
        )
    except (ValueError, NotImplementedError) as e:
        mq5_status = f"not_supported: {e}"
        log(f"  mq5 export skipped: {e}")

    pine_path, pine_status = None, "ok"
    try:
        pine_path = export_pine(
            out_dir / f"validated_{winner['name']}.pine",
            name=winner["name"], symbol="XAUUSD", timeframe="M15",
            params=winner["best_params"], family=winner["family"],
        )
    except (ValueError, NotImplementedError) as e:
        pine_status = f"not_supported: {e}"
        log(f"  pine export skipped: {e}")

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
        "run_dir":            str(run_dir),
        "html_report":        html_path,
        "pdf_report":         pdf_path,
        "pdf_status":         pdf_status,
        "mq5_file":           mq5_path,
        "mq5_export_status":  mq5_status,
        "pine_file":          pine_path,
        "pine_export_status": pine_status,
        "log_file":           str(log_path),
        "elapsed_sec":        round(time.time() - t0, 1),
    }
    log_path.write_text("\n".join(log_lines), encoding="utf-8")
    print(json.dumps(verdict, indent=2, default=str))
    return verdict


if __name__ == "__main__":
    csv = sys.argv[1] if len(sys.argv) > 1 else None
    main(csv)
