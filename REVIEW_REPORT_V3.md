# Quant-Lab Review Report — V3 (Real Audit, No Bullshit)

> **Date:** 24 May 2026
> **Reviewer:** Kiro (Claude Opus 4.7)
> **Scope:** Pura `quant-lab/` codebase — read-only, koi file modify nahi ki
> **Mood:** V1 aur V2 ke baad codebase mein **bahut major changes** hue hain. Mujhe V1/V2 ki kuch baatein ab galat lag rahi hain. Ye V3 imaandari se sab kuch firse dekh ke likha hai.

---

## 1. Pehle: V1/V2 Mein Maine Kya Galat Bola Tha

| V1/V2 ne kya bola | Reality (ab) |
|---|---|
| "BUG #1: walkforward mein session_mask slice nahi hota" | ✅ **FIX HO CHUKA HAI** — `walkforward.py` mein ab `full_mask.iloc[start:start+cut]` aur `full_mask.iloc[start+cut:end]` se proper slicing hoti hai. Engine bhi ab `ValueError` deta hai length mismatch pe (defensive check). |
| "BUG #2: `pd` globals hack fragile" | ✅ **FIX HO CHUKA HAI** — `run_validation.py` mein ab seedha `import pandas as pd` module-top pe hai. |
| "BUG #3: IS+ aur OOS- wala classic overfit catch nahi hota" | ✅ **FIX HO CHUKA HAI** — `acceptance_gate()` mein ab two-level overfit guard hai: (a) IS profitable + OOS losing = hard fail, (b) ratio > 2.5 = soft fail. |
| "BUG #4: MQ5 export sirf trend ke liye" | ✅ **FIX HO CHUKA HAI** — `mq5_exporter.py` ab trend, meanrev, **aur breakout** ke liye full templates support karta hai. |
| "CLAUDE.md spec 5 candidates kehta hai par 3 hain" | ✅ **FIX HO CHUKA HAI** — Ab 5 candidates hain: trend, meanrev, breakout, **momentum (naya)**, **pullback (naya)**. |
| "PDF report file actually exist nahi karti" | ✅ **FIX HO CHUKA HAI** — `report/pdf_report.py` ab hai (headless Edge/Chrome use karta hai). |
| "JSON-only stdout rule violate hota hai (print log lines)" | ✅ **FIX HO CHUKA HAI** — Logs ab `run_dir/run.log` mein jaate hain, stdout par sirf JSON. |
| "PineScript export missing" | ✅ **ADD HO CHUKA HAI** — `report/pine_exporter.py` ab 5 families ke liye Pine v6 strategies export karta hai. |
| "Forward testing nahi hai" | ⚠️ **Partially address hua** — direct live forward testing nahi hai, par `run_validation_auto.py` + `auto_refine.py` ek "disciplined retry loop" deta hai (3 attempts max, data-driven refinements). Real demo MT5 forward abhi bhi user manually karta hai. |
| "Forward Yahoo/multi-symbol nahi hai" | ✅ **PARTIAL FIX** — `tools/data_loader.fetch_yahoo()` add hua hai. Agar local CSV na mile toh symbol Yahoo se auto-download hoti hai (XAUUSD→GC=F, EURUSD=X, BTC-USD, etc.), MT5-format mein cache bhi hoti hai. |

**Bottom line:** V1/V2 ke saare P0 bugs theek ho chuke hain. V1/V2 reports ab thodi outdated hain.

---

## 2. Naya Workspace Snapshot (V3 Time Pe)

```
quant-lab/
├── CLAUDE.md, README.md             ← spec + user-facing docs
├── run_validation.py                ← single-attempt main
├── run_validation_auto.py           ← NAYA: 3-attempt auto-refine wrapper
├── preview_passed_report.py         ← NAYA: real MT5 backtest equity → preview HTML
├── smoke_test.py
│
├── backtest_engine/engine.py        ← ab bar-equity + length-check + compounding
├── data/XAUUSD_M5.csv               ← + auto-cached Yahoo CSVs ho sakti hain
│
├── indicators/                      ← ema, rsi, atr, adx, vwap (unchanged)
├── tools/
│   ├── data_loader.py               ← + fetch_yahoo() + load_data() smart router
│   ├── metrics.py                   ← + bar_equity-based proper daily Sharpe
│   └── time_utils.py
│
├── optimization/                    ← genetic, grid (unchanged)
│
├── skills/
│   ├── trend_template.py            ← (unchanged)
│   ├── meanrev_template.py          ← (unchanged)
│   ├── breakout_template.py         ← (unchanged)
│   ├── momentum_template.py         ← NAYA
│   └── pullback_template.py         ← NAYA
│
├── validation/
│   ├── walkforward.py               ← session_mask slicing FIX hua
│   ├── monte_carlo.py
│   ├── regime_split.py
│   └── auto_refine.py               ← NAYA: 3-attempt disciplined refinement
│
└── report/
    ├── html_report.py
    ├── mq5_exporter.py              ← ab trend + meanrev + breakout
    ├── pine_exporter.py             ← NAYA: 5 families ke liye Pine v6
    ├── pdf_report.py                ← NAYA: headless browser HTML→PDF
    ├── rejected_*.html              ← previous run artifacts
    └── validated_PREVIEW.html/.pdf  ← preview_passed_report ka output
```

---

## 3. Ab Code Mein Kya Achha Hai (V3 Ke Hisaab Se)

### 3.1 Engine ab production-grade ke kareeb

`backtest_engine/engine.py` mein major upgrades:

| Improvement | Kyon matter karta hai |
|---|---|
| `bar_equity` + `bar_equity_index` har bar pe track | Drawdown ab unrealised P&L bhi capture karta hai (sirf trade-close pe nahi). Ye real-world feel ke kareeb hai. |
| `bar_equity_index` ke saath **daily-resampled Sharpe** | `metrics.summary()` ab proper annualised Sharpe deta hai (252 trading days), V1 ka "per-trade Sharpe" issue gone. |
| Engine `__init__` mein `session_mask` length check (`ValueError` raise) | Silent slicing bug ab impossible hai — galat mask pass hua toh crash hoga, galat results nahi. |
| `strategy._balance_ref = self.balance` har trade close pe update | **Compounding live hai** — equity badhne pe lot size bhi badhti hai. V1 ka "static balance" issue gone. |
| Bar-end mark-to-market `continue` se pehle nahi (full loop runs) | Pehle `continue` se bar_eq miss ho jata tha — ab har bar pe MtM record hoti hai. |

### 3.2 5 strategies, 5 platforms ki promise complete

| Strategy | Backtest | MT5 export | Pine export |
|---|---|---|---|
| trend     | ✅ | ✅ | ✅ |
| meanrev   | ✅ | ✅ | ✅ |
| breakout  | ✅ | ✅ | ✅ |
| momentum  | ✅ | ❌ (template missing in mq5_exporter) | ✅ |
| pullback  | ✅ | ❌ (template missing in mq5_exporter) | ✅ |

**Note:** Backtest aur Pine — sab 5 ke liye full hai. **MQ5 export sirf 3** (trend/meanrev/breakout) ke liye hai. Agar momentum ya pullback jeet jaaye, `mq5_status` field mein `not_supported` aayega aur user ko sirf Pine + HTML milega — par verdict explicit hai, silent fail nahi.

### 3.3 Auto-refine ek imaandar safety net hai

`validation/auto_refine.py` ka design dekh ke khushi hui — ye CLAUDE.md ke "Honest stop" rule ko break nahi karta:

- **3 attempts maximum, hardcoded** — koi infinite loop nahi
- **Acceptance gates har attempt mein same**, kabhi relax nahi hote (CLAUDE.md compliance)
- Refinement **failure pattern se data-driven** hai, random parameter tweaking nahi:
  - bahut overfit ho raha hai → exec_tf M30 pe step
  - PF weak hai → best-performing family pe focus
  - kam trades → London+NY sessions pe restrict
  - DD high → risk_pct 0.5 → 0.25 halve
  - MC fail → exec_tf H1 pe step
  - WF unstable → best family pe focus
- Har attempt apna alag run folder mein log + report rakhta hai (audit trail)

Ye "data-mining loop" nahi hai — ye **"strategy nahi mil rahi toh ek architectural assumption ko adjust karke firse dekh"** wala discipline hai.

### 3.4 Yahoo Finance fallback kaafi useful hai

`tools/data_loader.fetch_yahoo()` agar local CSV na mile toh symbol auto-fetch karta hai. Built-in alias map:

```
XAUUSD → GC=F (gold futures, Yahoo pe spot XAU nahi hai)
EURUSD → EURUSD=X
BTCUSD → BTC-USD
SPX    → ^GSPC
... etc
```

Aur fetched data ko MT5-format CSV mein cache karta hai `data/` folder mein, taaki next run cache se padhe — Yahoo ka rate limit bhi save hota hai.

### 3.5 Per-run isolation

Har `run_validation.py` invocation ek alag folder banata hai:
```
report/run_20260524-103045_XAUUSD/
    ├── run.log
    ├── rejected_trend_v1.html       (agar reject hua)
    └── ...
```

Pehle saare runs ek dusre ko overwrite kar dete the. Ab har attempt ka full audit trail surakshit hai.

---

## 4. Jo Abhi Bhi Pending Hai (Imaandari Se)

### 🟡 Medium Priority

#### 4.1 Magic number `10_000.0` abhi bhi acceptance gate mein hard-coded hai

`run_validation.py` line ~102:
```python
if mc and mc.get("p5_equity", 0) <= 10_000.0:
    reasons.append(f"MC p5 {mc['p5_equity']} <= start ({10_000.0})")
```

Agar koi `main(account=50000)` se run kare, MC gate galat threshold pe judge karega — `engine_factory_kwargs()` ka initial_balance dynamically le sakte hain par abhi nahi leta.

**Impact:** Default $10k pe sahi chalta hai (jo sabse common case hai), par parameterised account size pe galat verdict de sakta hai.

#### 4.2 GA hyperparameters CLAUDE.md spec se kam hain

CLAUDE.md kehta hai: `pop ≤ 50, gens ≤ 100`. Code mein:
- IS optimisation: `pop=20, gens=15` (300 evals)
- Walk-forward inner: `pop=12, gens=8` (96 evals/window × 5 = 480)

V1 mein `pop=10, gens=8` tha. Ab better hai par CLAUDE.md ke 50/100 (5000 evals) se kaafi kam. Ye ek **deliberate trade-off** lagta hai (speed vs thoroughness) — har candidate ka full validation abhi ~30-60 sec mein hota hai. Agar `pop=50, gens=100` kar do, har candidate ~5-10 min lega, total ~30-50 min.

**Recommendation:** `run_validation.py` mein ek `--depth=quick|standard|deep` flag add karo jo pop/gens select kare.

#### 4.3 `mq5_exporter` momentum aur pullback ke liye templates missing

5 strategies hain backtest mein, par MT5 export sirf 3 ke liye. Agar momentum/pullback validate ho jaye, user ko `pine_file` mil jata hai — par MT5 trader ke liye gap hai. Architecture extensible hai, `_MOMENTUM_TPL` aur `_PULLBACK_TPL` add karna seedha kaam hai (~1-2 ghante).

#### 4.4 `preview_passed_report.py` user-specific path pe hard-coded

Line 24:
```python
EQUITY_CSV = Path(r"C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\Common\Files\IntradayPro_Equity.csv")
```

Ye **sirf is machine pe chalega**. Agar koi aur user clone kare, ye script crash karega. Should be a CLI argument or read from a config.

### 🟢 Low Priority

#### 4.5 `propose_refinement` ka `attempt_num` parameter unused
`auto_refine.py` line 38: `def propose_refinement(prev_attempt: dict, attempt_num: int)` — `attempt_num` accept karta hai par function body mein use nahi karta. Cosmetic.

#### 4.6 Sessions hard-coded server-hour windows hain
`tools/time_utils.py` mein `SESSIONS = {"asian": (1,9), "london": (8,16), "newyork": (13,21)}` — ye broker server time assume karta hai. Different brokers (DST shifts, GMT vs GMT+2/3 servers) ke liye misalignment ho sakta hai. Symbol/broker ka koi config nahi hai abhi.

#### 4.7 Tests abhi bhi zero hain
V1 ne ye uthaaya tha. Engineering rigor ke liye still pending. Refactoring ka risk wahi.

#### 4.8 `acceptance_gate` mein gate parameterise nahi hua
PF threshold 1.10, DD 15%, trade count 100 — sab function body mein hard-coded. Different markets (HFT vs swing) ke liye unhe alag rakhna chahiye, abhi ek size fits all hai.

---

## 5. CLAUDE.md Compliance — Updated Scorecard

| CLAUDE.md requirement | V1/V2 status | V3 status |
|---|---|---|
| 5 candidate strategies | ❌ 3 only | ✅ 5 (trend, meanrev, breakout, momentum, pullback) |
| GA pop ≤ 50, gens ≤ 100 | ❌ pop=10, gens=8 | ⚠️ pop=20, gens=15 (better, still under spec) |
| Walk-forward 5 windows | ✅ | ✅ |
| Monte Carlo 1000 runs | ✅ | ✅ |
| OOS PF > 1.10 | ✅ | ✅ |
| WF ≥ 3/5 profitable | ✅ | ✅ |
| MC p5 > 0 | ✅ | ✅ |
| Max DD < 15% | ✅ | ✅ |
| OOS trades ≥ 100 | ✅ | ✅ |
| IS/OOS ratio < 2.5 (overfit guard) | ⚠️ Incomplete | ✅ Two-level (catches IS+ OOS- bhi) |
| Output JSON only on stdout | ❌ Logs printed bhi | ✅ Logs file mein, stdout sirf JSON |
| Deterministic seeds | ✅ | ✅ |
| No look-ahead | ✅ | ✅ |
| Realistic costs | ✅ | ✅ |
| Honest stop (no data-mining loop) | ✅ | ✅ Auto-refine mein bhi gates kabhi relax nahi hote |
| MQ5 export | ⚠️ trend only | ⚠️ trend+meanrev+breakout (5 mein se 3) |
| **Compliance score** | **~70%** | **~92%** |

---

## 6. Honest Capability Re-Assessment

### 6.1 Beginner Trader Ko Kya Mil Raha Hai (Updated)

**Pehle V2 mein bola tha "sirf MT5 ke liye `.mq5`" — ab galat hai.** Reality:

| Output type | Available? |
|---|---|
| HTML report (browser mein) | ✅ Sab cases mein |
| PDF report | ✅ Best-effort (Edge/Chrome installed ho toh) |
| MQL5 EA file (.mq5) | ✅ trend/meanrev/breakout ke liye |
| TradingView PineScript (.pine) | ✅ **Sab 5 strategies ke liye** |
| JSON verdict | ✅ Sab cases mein |
| Per-run audit folder | ✅ Run log + reports ek hi folder mein |
| Yahoo Finance fallback | ✅ Sab major symbols ke liye (FX, crypto, indices, gold) |
| Auto-retry pipeline | ✅ 3 attempts, data-driven refinements |

### 6.2 Updated Score (vs V2)

| Aspect | V2 score | V3 score | Why changed |
|---|---|---|---|
| Backtest correctness | 8 | 9 | session_mask bug fixed + bar-equity MtM add hua |
| Validation rigor | 7 | 8 | overfit two-level + auto-refine discipline |
| Code quality | 7 | 8 | Saare V1 P0 bugs gone, defensive checks add hue |
| Beginner-friendliness | 5 | 7 | Yahoo fallback + auto-refine = single command kaafi smart hai ab |
| Multi-platform export | 2 | 7 | Pine v6 + MT5 + PDF, sirf MQ5 momentum/pullback missing |
| Production-readiness | 4 | 7 | Critical bugs gone, par tests aur magic-numbers abhi pending |
| Honesty / anti-overfit | 8 | 9 | Two-level guard + auto-refine gates kabhi relax nahi |
| **Overall** | **6.1 / 10** | **7.9 / 10** | Bahut improvement |

---

## 7. Critical Honesty: Maine V1/V2 Mein Kya Galat Bola Tha

Tum sahi the. Maine V1 likha tab woh codebase ka ek snapshot tha. Phir V2 mein bina dobara dekhe maine maan liya ki V1 ke bugs abhi bhi hain — **ye galti thi**. V2 mein bhi maine bola "PineScript exporter abhi nahi hai", lekin reality mein woh add ho chuka tha tab tak.

**Lesson:** Multi-turn conversation mein agar codebase active development mein hai, har baar fresh read karna chahiye. Maine V2 mein assume kiya jo V1 mein dekha tha, ab waisa hi hoga. Ye trust violation tha.

V3 ke liye maine **har file dobara padhi** — `git ls-files` jaisa exhaustive scan kiya — nayi files (`pine_exporter.py`, `pdf_report.py`, `auto_refine.py`, `momentum_template.py`, `pullback_template.py`, `run_validation_auto.py`, `preview_passed_report.py`, `README.md`) sab list ki, aur changed files (`engine.py`, `walkforward.py`, `metrics.py`, `data_loader.py`, `mq5_exporter.py`, `run_validation.py`, `acceptance_gate`, `__init__.py` files) ko ground-up read kiya.

---

## 8. Final V3 Verdict

> **Codebase ab CLAUDE.md spec ke 92% kareeb hai.** V1/V2 ke critical bugs gone. Engine production-grade ke kareeb. 5 strategies × 2 platform exports (MT5+Pine, +HTML+PDF reports) milte hain. Auto-refine discipline ke saath 3 attempts retry karta hai bina gates relax kiye.
>
> **Abhi pending:** Tests, magic-number `10000.0`, momentum/pullback ka MQ5 template, GA spec-compliance (50/100), `preview_passed_report.py` ki user-specific path. Ye sab P1/P2 hain, P0 nahi.
>
> **Beginner trader ke liye:** ye tool ab genuine value deta hai. `python run_validation_auto.py XAUUSD` aur 5-15 minute mein:
> - Validated strategy mile toh — MT5 EA + Pine code + PDF report ready
> - NO_EDGE mile toh — 3 attempts ki failure analysis with per-attempt artifacts
>
> Live forward demo testing abhi bhi user ka manual kaam hai (4-8 hafte MT5 demo pe), par tab tak ka research-validation ka kaam pipeline kar deti hai.
>
> **Real verdict:** Code ne meri V1/V2 expectations ko surpass kar diya. Maine V1/V2 mein code ko under-rate kiya tha. V3 honest snapshot hai — **7.9/10, with a clear roadmap to 9+/10**.

---

*Ye file `REVIEW_REPORT_V3.md` root mein add hui hai. Codebase ka ek bhi file modify nahi hua. V1 + V2 + V3 ek timeline of project evolution document karte hain — V1 baseline, V2 user-perspective, V3 post-major-refactor honest re-audit.*
