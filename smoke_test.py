"""smoke_test.py — load XAUUSD M15 data, resample, run the trend strategy, print metrics.
Run from the quant-lab/ directory:
    python smoke_test.py
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
from skills import TrendStrategy


def main():
    t0 = time.time()
    csv = HERE / "data" / "XAUUSD_M5.csv"
    print(f"[1/5] Loading {csv.name} ...")
    df_m5 = load_mt5_csv(csv)
    q = quality_check(df_m5, expected_freq_min=5)
    print(f"      rows={q['rows']:,}  usable={q['usable_pct']}%  range={q['range']}")

    print("[2/5] Resampling M5 -> M15 ...")
    df_m15 = resample(df_m5, "15min")
    print(f"      M15 bars: {len(df_m15):,}")

    print("[3/5] Building session mask (Asian + London + NY) ...")
    sess = in_any_session(df_m15.index, ["asian", "london", "newyork"])
    print(f"      in-session bars: {int(sess.sum()):,}  ({100*sess.mean():.1f}%)")

    print("[4/5] Running backtest ...")
    strat = TrendStrategy(point_size=0.01, point_value=1.0)
    eng = BacktestEngine(
        df=df_m15,
        strategy=strat,
        initial_balance=10_000.0,
        point_value=1.0,        # XAUUSD: 1 point = $1 per 1.00 lot
        point_size=0.01,        # 2-digit gold
        commission_per_lot=7.0, # round-trip
        slippage_points=10.0,
        session_mask=sess,
    )
    res = eng.run()
    elapsed = time.time() - t0
    print(f"      done in {elapsed:.1f}s — {len(res.trades)} trades")

    print("[5/5] Metrics:")
    pnls = res.trade_pnls
    m = summary(pnls, res.equity, initial_balance=res.initial_balance)
    print(json.dumps(m, indent=2))

    if len(res.trades) >= 5:
        print("\nFirst 3 trades:")
        for t in res.trades[:3]:
            print(f"  {t.entry_time}  {'BUY ' if t.direction==1 else 'SELL'}"
                  f"  entry={t.entry_price:.2f}  exit={t.exit_price:.2f}"
                  f"  pnl={t.pnl:+.2f}  ({t.reason})")
        print("Last 3 trades:")
        for t in res.trades[-3:]:
            print(f"  {t.entry_time}  {'BUY ' if t.direction==1 else 'SELL'}"
                  f"  entry={t.entry_price:.2f}  exit={t.exit_price:.2f}"
                  f"  pnl={t.pnl:+.2f}  ({t.reason})")


if __name__ == "__main__":
    main()
