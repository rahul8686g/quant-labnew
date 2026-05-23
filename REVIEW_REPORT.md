# Quant-Lab Codebase Review Report (Hindi)

> **Date:** 23 May 2026
> **Reviewer:** Kiro (Claude Opus 4.7)
> **Scope:** Pura `quant-lab/` folder — read-only review, koi code change nahi
> **Purpose:** Code quality, design soundness, bugs, aur CLAUDE.md ke saath alignment ka assessment

---

## 1. Executive Summary (Ek Nazar Mein)

| Pehlu | Verdict | Ek line mein |
|---|---|---|
| Architecture | ✅ Achha | Saaf folder separation, single-responsibility, kahin god-file nahi |
| Documentation | ✅ Achha | `CLAUDE.md` clear hai aur har module mein docstring hai |
| Look-ahead safety | ✅ Mostly OK | Engine bar-close pe decide karta hai, breakout `shift(1)` use karta hai |
| Validation rigor | ⚠️ Partial | WF + MC + regime hain, lekin GA hyperparameters CLAUDE.md ke pop=50/gen=100 se kaafi kam set hain |
| CLAUDE.md alignment | ⚠️ Mismatch | Spec 5 candidates kehta hai, code mein sirf 3 hain |
| Production-ready bugs | ❌ 2 critical | `session_mask` slicing bug aur `pd` import scoping issue |
| Test coverage | ❌ Absent | Koi unit/integration test nahi |

**Bottom line:** Foundation solid hai, par 2 critical bugs hain jo silent-fail kar sakte hain (galat results de sakte hain bina error ke). Inhe theek karne se pehle koi bhi "VALIDATED" verdict trust nahi karna chahiye.

---

## 2. Folder-Wise Strengths

### 2.1 `backtest_engine/engine.py`
- **No-lookahead invariant strict hai** — `on_bar(i, ...)` ko bar `i` ka close milta hai, trade `i+1` ke open pe execute hota hai. SL/TP intrabar `i+1` pe check hote hain. Ye bilkul correct hai.
- **Realistic cost model**: spread, commission (round-trip x2), slippage — sab apply hote hain. Free entry/exit ki galti nahi.
- **Force-flat at EOD**: data ke aakhir mein open position ko close kar deta hai — equity curve mein hanging position nahi.
- **Deterministic** — seed se RNG initialize hota hai.
- Code well-documented hai, dataclasses use ki gayi hain.

### 2.2 `indicators/`
- Saare indicators **vectorised** hain (pandas/numpy), explicit loops nahi.
- **Wilder smoothing** sahi tarike se RSI, ATR, ADX mein lagi hai (`alpha = 1/period`) — MetaTrader ke iRSI/iATR/iADX se match karega.
- ATR ka `true_range` separate function hai aur ADX usi ko reuse karta hai — clean reuse.
- VWAP daily anchor ke saath, `to_period(anchor)` se group — sahi reset logic.
- ⚠️ Minor: `vwap` aur `supertrend` (CLAUDE.md mein listed) hain, par actively kahin use nahi ho rahe. `__init__.py` mein bhi nahi exported.

### 2.3 `tools/`
- `data_loader.quality_check` OHLC sanity, gaps, duplicates check karta hai — mature.
- `metrics.summary` ek hi call mein PF, Sharpe, Sortino, DD, expectancy deta hai — clean API.
- `time_utils` session masks correctly OR-combine karta hai.

### 2.4 `optimization/`
- `GeneticOptimizer` mein elitism + crossover + mutation sab hain. Mutation Gaussian span-relative hai (smart).
- `ParamSpec` clean abstraction hai — float/int/step support karta hai.
- `GridOptimizer` chhoti spaces ke liye fallback hai — achhi engineering.

### 2.5 `validation/`
- `walkforward` non-overlapping windows banata hai, har window mein IS-optimise → OOS-test karta hai. Iska principle sahi hai.
- `monte_carlo` trade-order shuffle karta hai (sequence luck check), p5/p50/p95 equity aur DD return karta hai.
- `regime_split` EMA slope se uptrend/downtrend/range bucket karta hai — simple par usable.

### 2.6 `report/`
- `html_report.py` self-contained HTML banata hai — koi external JS dependency nahi, equity + underwater DD canvas pe draw karta hai. Portable hai.
- `mq5_exporter.py` validated trend strategy ko compilable `.mq5` file mein convert karta hai — pipeline ka real value-add.

---

## 3. Critical Issues (Inhe Pehle Theek Karna Hai)

### 🔴 BUG #1 — `walkforward` mein `session_mask` indexing tut sakta hai

**File:** `validation/walkforward.py` line ~28 + `backtest_engine/engine.py` line ~150

**Kya ho raha hai:**

`run_validation.py` mein:
```python
wf = walkforward(df_full, cls, opt_factory, specs, ...,
                 engine_kwargs={**ekw, "session_mask": session_mask}, ...)
```

`session_mask` poori `df_m15` ke liye banaya gaya hai (full length).

`walkforward.py` mein har window ke liye `is_df = win.iloc[:cut]` slice banta hai, par `engine_kwargs` waisa ka waisa pass hota hai — yaani `session_mask` sliced nahi hota.

`engine.py` line:
```python
if self.session_mask is not None and not bool(self.session_mask.iloc[i + 1]):
```

Yahan `iloc[i+1]` positional index hai. Mask poori df ka hai par `df` window ki slice hai → indices align nahi karte. Wrong bars ka session check hota hai.

**Asar:** Walk-forward results subtly galat. Aksar pass hone wala window fail dikhega ya vice versa. Verdict pe direct effect.

**Fix idea (apply nahi karna ab, suggestion ke taur pe):** walkforward mein har window ke liye `mask_slice = session_mask.iloc[start:end].iloc[:cut]` aur `oos_mask` similarly slice karke pass karein.

---

### 🔴 BUG #2 — `evaluate_candidate` mein `pd` global hack fragile hai

**File:** `run_validation.py`

```python
def evaluate_candidate(cand: dict, df_full: pd.DataFrame, ...):  # type: ignore[name-defined]
    ...

def main(...):
    import pandas as pd
    globals()["pd"] = pd
```

`pd` function-level mein use hota hai (type hint mein) lekin module-level pe import nahi hai. `main()` baad mein globals mein inject karta hai. Type-hint evaluation `from __future__ import annotations` ki wajah se string-based hai isliye runtime mein crash nahi karega — par ye anti-pattern hai aur:
- `evaluate_candidate` ko standalone test karna mushkil ho jata hai
- Linter/type checker confuse karega
- Agar future mein koi `from __future__ import annotations` hata de, runtime crash

**Fix idea:** seedha file ke top pe `import pandas as pd` likh dein.

---

### 🟡 BUG #3 — IS/OOS overfit guard incomplete hai

**File:** `run_validation.py` `acceptance_gate()` function:

```python
if is_metrics and is_metrics["net_profit"] > 0 and metrics_oos["net_profit"] > 0:
    ratio = is_metrics["net_profit"] / metrics_oos["net_profit"]
    if ratio > 2.5:
        reasons.append(...)
```

**Problem:** Sirf tab check hota hai jab dono profitable hon. Sabse classic overfit case — IS profitable, OOS negative — ko ye **catch nahi karta**. Aisi strategy chup-chap pass ho sakti hai (jo CLAUDE.md ke "honest stop" rule ke khilaf hai).

**Recommendation:** Agar `is_metrics["net_profit"] > 0` aur `metrics_oos["net_profit"] <= 0`, toh straight-up overfit fail mark karein — bhale hi baaki gates pass ho rahe hon.

---

### 🟡 BUG #4 — `mq5_exporter` non-trend families ke liye silently skip hota hai

**File:** `run_validation.py`:

```python
if winner["family"] == "trend":
    mq5_path = export_mq5(...)
```

**Problem:** Agar `meanrev_v1` ya `breakout_v1` jeet jaata hai, `mq5_path = None`. User ko VALIDATED verdict milta hai par MT5 mein trade karne ke liye koi EA nahi. CLAUDE.md ke output JSON mein `mq5_path` field promised hai.

**Recommendation:** Ya toh `_MEANREV_TPL` aur `_BREAKOUT_TPL` add karein, ya verdict mein `"mq5_export": "not_supported_yet"` jaisa explicit field rakhein.

---

## 4. CLAUDE.md ke Saath Mismatches

| CLAUDE.md kehta hai | Code mein actually hai |
|---|---|
| **5 candidate strategies** generate karo | Sirf **3** (`trend`, `meanrev`, `breakout`) |
| GA: `pop ≤ 50, gens ≤ 100` | Code mein `pop=10, gens=8` (IS) aur `pop=10, gens=6` (WF) — **bahut chhota**, optimization shallow hai |
| **Monte Carlo 1000 runs** | Code mein 1000 hai ✅ |
| Walk-forward **5 windows** | 5 hai ✅ |
| Output **JSON only**, no prose | `run_validation.py` JSON ke pehle `print(...)` log lines bhi deta hai |
| **PDF report** | `report/pdf_report.py` mention hai par actually exist nahi karta |

**Asar:** Population/generation itni chhoti hone se GA aksar local optimum pe atak jata hai. `pop=10` ke saath sirf 8 generations — effectively 80 fitness evaluations per candidate. Strategy ki real edge nikaalne ke liye yeh under-powered hai. Smoke testing ke liye theek hai, real validation ke liye nahi.

---

## 5. Design-Level Observations

### 5.1 Position sizing static balance use karta hai
Sab strategy templates mein:
```python
self._balance_ref = 10_000.0   # updated externally if you want compounding sizing
```
Comment kehta hai "externally updated", par engine ye kabhi update nahi karta. Yaani **risk = 0.5% of starting balance, hamesha** — compounding nahi ho raha. Lambi backtests mein iska matlab equity badhe par lot size constant rahegi (effective risk % ghatega).

Ye bug nahi hai, par CLAUDE.md kehta hai "$10k account, 0.5% risk/trade" — ambiguous hai compounding ke baare mein. Agar realistic live trading replicate karna hai, balance ko update karna chahiye.

### 5.2 Equity curve trade-based hai, bar-based nahi
`equity` array sirf trade close hone pe update hoti hai. Iska matlab:
- Open position ke andar ke unrealised drawdowns metrics mein nahi aate
- Sharpe `np.diff(eq)/eq[:-1]` per-trade returns hain, daily nahi — `periods_per_year=252` thoda misleading hai (252 trading days ke liye, par yahan 252 trades nahi)

**Suggestion:** Sharpe annualization ko trade frequency se derive karein, ya document karein ki ye "per-trade Sharpe" hai.

### 5.3 Spread bar `i+1` se aata hai signal time pe
`engine._spread_price(i+1)` — yaani entry bar ka spread use hota hai. Strict no-lookahead view se ye OK hai (spread market state hai, signal nahi), par ek conservative implementation `bar i` ka spread use kar sakta hai.

### 5.4 `breakout_template` mein `entry_ref = row["close"]` use hota hai SL/TP placement ke liye, jabki actual fill `i+1` open pe hota hai. Iska matlab SL/TP price ekdam fill price se thoda offset hote hain. Ye realistic hai (system signal time pe SL/TP set karta hai), par engine intrabar SL/TP check fill price ke around kar raha hai — minor inconsistency. Practically ignorable.

### 5.5 GA parent pool slicing
```python
p1 = self.rng.choice(pop[: self.elite_n * 3])
```
Agar `elite_n * 3 > population`, slicing safe hai (Python silently full list deta hai), par effective elitism dilute ho jaata hai. `pop=10, elite_frac=0.2` → `elite_n=2`, `elite_n*3=6`. OK hai. Bas yaad rakhna chahiye agar future mein hyperparams change ho.

### 5.6 Acceptance gate threshold drift
CLAUDE.md mein "MC 95% lower bound > 0" likha hai (yaani > 0 profit), code `p5_equity > initial_balance` check karta hai. Ye effectively same hai (p5_equity > 10000 = profit > 0), par `acceptance_gate` mein hard-coded `10_000.0` likha hai jabki engine kahin se bhi initial balance le sakta hai. Agar kabhi initial balance change hua, gate stale ho jayega.

```python
if mc and mc.get("p5_equity", 0) <= 10_000.0:   # <-- magic number
```

**Suggestion:** Initial balance ko parameter banao.

---

## 6. Code Quality (Chote Lekin Achhe Suggestions)

| # | Observation | File |
|---|---|---|
| 1 | `engine_factory_kwargs()` ek module-level constant ho sakta hai (recompute har baar) | `run_validation.py` |
| 2 | `summary()` mein `periods_per_year=252` hard-coded hai, parameterise karna achha rahega | `tools/metrics.py` |
| 3 | `quality_check` mein "usable" calculation `bad_ohlc + dup` ko subtract karta hai par overlap ko ignore karta hai (kyon ki ek row dono ho sakti hai) | `tools/data_loader.py` |
| 4 | `regime_split` mein `regime.asof(t.entry_time)` exception handle karta hai par `r="range"` default kabhi-kabhi misleading ho sakta hai | `validation/regime_split.py` |
| 5 | HTML report inline CSS aur JS embed karta hai — portable hai par maintainability ke liye templates folder use kar sakte hain | `report/html_report.py` |
| 6 | Konsa `Strategy` base class `params` class-level dict hai — agar multiple instances same dict mutate karein, cross-instance leak ho sakta hai. Lekin code `__init__` mein `{**self.params, **params}` se naya dict banata hai, isliye safe — bas note rakhna |
| 7 | `from __future__ import annotations` zyadatar files mein hai (achha) par `regime_split.py` mein nahi |

---

## 7. Security / Correctness Concerns

- ✅ Koi `eval()` / `exec()` user input pe nahi ho raha.
- ✅ MQ5 export template mein params normal `.format()` se interpolate hote hain — par agar kabhi user-controlled string `params` mein aaye, MQ5 file mein injection ho sakti hai. Currently params GA se aate hain isliye safe.
- ✅ File paths `Path(out_path).parent.mkdir(parents=True, exist_ok=True)` se properly handle hote hain.
- ⚠️ CSV load karte time `read_csv(path, sep="\t")` — agar koi non-MT5 CSV diya jaye toh silently galat parse hoga. Header validation add karne ka faayda hoga.

---

## 8. Test Coverage

**Status: ❌ Zero unit tests.**

Sirf `smoke_test.py` hai jo end-to-end ek strategy chalata hai. Iska matlab:
- Indicator correctness MT5 ke against verify nahi hai (sirf claim hai)
- Engine ke edge cases (empty trades, single-bar window, EOD position) test nahi hote
- Refactoring kabhi karna ho toh confidence nahi rahega

**Recommendation:** Kam-se-kam in pe `pytest` lagao:
- Indicators: known input → known output (MT5 reference values se compare)
- Engine: ek deterministic 100-bar dataset pe expected trade list
- Acceptance gate: synthetic metrics dict pe sab fail-paths trigger ho rahe hain ya nahi

---

## 9. Reproducibility Audit

| Random source | Seeded? | Status |
|---|---|---|
| `BacktestEngine` `rng` | seed=42 default | ✅ |
| `GeneticOptimizer` `rng` | seed=42 default | ✅ |
| `monte_carlo` rng | seed=42 default | ✅ |
| Numpy operations | implicit deterministic | ✅ |

**Achha:** Pura pipeline same seed ke saath same output dega — CLAUDE.md ke "deterministic seeds" requirement satisfied.

---

## 10. Recommendations (Priority Order)

| Priority | Item | Effort |
|---|---|---|
| 🔴 P0 | `session_mask` slicing bug walkforward mein theek karein | Low (10 min) |
| 🔴 P0 | `pd` import seedha module-top pe karein | Trivial |
| 🟡 P1 | Overfit guard ko strengthen karein (IS+ aur OOS- bhi flag karein) | Low |
| 🟡 P1 | GA hyperparameters CLAUDE.md ke spec (pop=50, gens=100) ke close lao | Low (CPU cost trade-off) |
| 🟡 P1 | 5 candidates banao (CLAUDE.md compliance) — e.g. trend variants ya mean-rev VWAP | Medium |
| 🟢 P2 | Unit tests add karein (indicators + engine + gate) | Medium-High |
| 🟢 P2 | `meanrev` aur `breakout` ke liye MQL5 templates likhain | Medium |
| 🟢 P2 | Initial balance ko gate mein parameterise karein, magic number hatao | Low |
| 🟢 P3 | `pdf_report.py` actually banao ya CLAUDE.md se hatao | Low |
| 🟢 P3 | Compounding-aware position sizing (engine `balance` ko strategy mein push karein) | Medium |

---

## 11. Files Reviewed

| File | Lines (approx) | Verdict |
|---|---|---|
| `CLAUDE.md` | ~150 | Strong spec |
| `run_validation.py` | ~190 | 2 bugs |
| `smoke_test.py` | ~60 | Clean |
| `backtest_engine/engine.py` | ~190 | Solid, minor notes |
| `backtest_engine/__init__.py` | 3 | OK |
| `indicators/ema.py` | ~10 | Clean |
| `indicators/rsi.py` | ~15 | Clean, Wilder-correct |
| `indicators/atr.py` | ~20 | Clean |
| `indicators/adx.py` | ~25 | Clean |
| `indicators/vwap.py` | ~20 | Clean, unused |
| `indicators/__init__.py` | 10 | OK |
| `tools/data_loader.py` | ~50 | Solid |
| `tools/metrics.py` | ~70 | Solid |
| `tools/time_utils.py` | ~30 | Solid |
| `optimization/genetic.py` | ~110 | Solid |
| `optimization/grid.py` | ~40 | Clean |
| `optimization/__init__.py` | 4 | OK |
| `validation/walkforward.py` | ~80 | 1 critical bug |
| `validation/monte_carlo.py` | ~50 | Clean |
| `validation/regime_split.py` | ~60 | Clean |
| `validation/__init__.py` | 4 | OK |
| `report/html_report.py` | ~180 | Solid |
| `report/mq5_exporter.py` | ~140 | Trend-only limitation |
| `report/__init__.py` | 4 | OK |
| `skills/trend_template.py` | ~95 | Solid |
| `skills/meanrev_template.py` | ~70 | Solid |
| `skills/breakout_template.py` | ~70 | Solid |
| `skills/__init__.py` | 5 | OK |

---

## 12. Final Verdict

> **Codebase ki neev majboot hai** — saaf separation, no-lookahead enforcement, realistic costs, deterministic seeds. CLAUDE.md ke spirit ko follow karne ki imaandar koshish dikhti hai.
>
> **Lekin abhi production-validation ke liye taiyaar nahi hai** — 2 critical bugs hain (session-mask slicing + import scoping), GA under-powered hai, aur 5 → 3 candidate mismatch hai. Ye sab silently galat verdict de sakte hain — jo CLAUDE.md ke "Never fabricate, never inflate" rule ka direct violation hai (anjaane mein hi sahi).
>
> **P0 fixes (~30 min ka kaam) ke baad ye codebase trustworthy validation pipeline ban jayegi.** Tab tak `smoke_test.py` ke results ko indicative samjho, final-verdict-grade nahi.

---

*Report ready. Koi code touch nahi hua. Agar tum chaho toh main inhi findings mein se jisko bole, fix bhi kar deta hoon.*
