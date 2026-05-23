# quant-lab

Autonomous trading-strategy validation pipeline for MetaTrader 5 / Python.

You give it OHLC data and a one-line strategy idea — it generates candidate
strategies, runs in-sample optimisation, walk-forward, Monte Carlo, regime
splits, applies a strict acceptance gate, and returns either a **VALIDATED**
strategy with a ready MQL5 EA + HTML report, or an honest **NO_EDGE**
verdict. It does not fabricate, does not curve-fit, and will reject rather
than approve a marginal strategy.

> **The brain of the project is [`CLAUDE.md`](./CLAUDE.md)** — read it first.
> Every rule, every threshold, every workflow phase is documented there.

---

## Quick start

```bash
# 1. drop an MT5-format OHLC CSV into data/
cp YOUR_SYMBOL.csv data/

# 2. smoke-test the engine
python smoke_test.py

# 3. full autonomous validation
python run_validation.py data/YOUR_SYMBOL.csv
```

Output: a JSON verdict + HTML reports under `report/`.

---

## Folder map

| Folder | What lives here |
|---|---|
| `data/`             | raw OHLC CSVs (MT5 tab-separated format) |
| `backtest_engine/`  | event-driven bar-by-bar simulator, no look-ahead |
| `indicators/`       | ema, rsi, atr, adx, vwap — vectorised, deterministic |
| `tools/`            | data loader, session helpers, performance metrics |
| `optimization/`     | genetic & grid search drivers |
| `validation/`       | walk-forward, Monte Carlo, regime-split |
| `skills/`           | strategy templates: trend, mean-reversion, breakout |
| `report/`           | HTML report generator + MQL5 EA exporter |

---

## Acceptance gate (every candidate must pass ALL)

| Check | Threshold |
|---|---|
| Out-of-sample profit factor | > 1.10 |
| Walk-forward windows profitable | ≥ 3 of 5 |
| Monte Carlo 5th percentile equity | > starting balance |
| OOS max drawdown | < 15% |
| OOS trade count | ≥ 100 |
| IS / OOS profit ratio | < 2.5× (overfit guard) |

If zero candidates survive → verdict **NO_EDGE** with the actual failure
metrics for each candidate. Honest stop. No data-mining loop.

---

## Stack

Python 3.10+, pandas, numpy. Nothing else. No web service, no cloud — runs
fully local. Designed to drop into Claude Code with `CLAUDE.md` so an AI
agent can run the pipeline end-to-end on a single prompt.

---

## Disclaimer

Backtest profitability does not guarantee live profitability. Always demo-
forward-test for 4–6 weeks before risking real capital. This is a research
tool, not financial advice.
