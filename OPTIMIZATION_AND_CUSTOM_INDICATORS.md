# Quant-Lab: Optimization Roadmap + Custom AI-Built Indicators

> **Date:** 24 May 2026
> **Author:** Kiro (Claude Opus 4.7)
> **Type:** Honest planning document — koi hype nahi, koi "guaranteed profit" nahi
> **Question Asked:** "Kya hum app ko optimise karke aur reliable + profitable bana sakte hain? Aur kya AI khud naye indicators build kar sakta hai naye math + statistics use kar ke?"
>
> **Short answer:** **Haan dono possible hain — par expectations realistic rakhne padenge.** Niche poora plan hai.

---

## Part 1 — Honest Reality Check (Pehle Yeh Padho)

### Kya hota hai aur kya nahi hota:

| Belief | Reality |
|---|---|
| "Naya indicator = naya profit" | ❌ Galat. 90% "secret indicators" wahi standard math hai naye naam ke saath. |
| "AI naya indicator bana sakti hai" | ✅ Sach. Real research areas hain — niche dekhenge. |
| "Naya indicator → guaranteed edge" | ❌ Galat. Novelty ≠ profitability. Novel + statistically tested + walk-forward validated = better candidate. |
| "Standard indicators (RSI/MA/MACD) useless hain" | ❌ Galat. Useless nahi, par sab use karte hain → edge thin hai. Custom features signal-to-noise behtar kar sakte hain. |
| "Better strategies = better profit" | ⚠️ Partial. Better validation = profit ka chance behtar. Profit khud market regime + execution + discipline pe depend karta hai. |

### Sabse important truth:

> **Edge sirf indicator se nahi aati. Edge aati hai: (a) data jo dusre nahi dekh paate, (b) execution jo dusre se faster ho, ya (c) statistical pattern jo dusre catch nahi karte. Custom indicators (c) category mein aate hain — yeh hard hai par possible hai.**

---

## Part 2 — App Ko Reliable + Profitable Banane Ka Roadmap

Yeh roadmap **3 levels** mein divide kiya hai. Har level ke saath specific files, code locations, aur expected impact hai.

---

### LEVEL 1 — Foundation Strengthening (Easy Wins, 1-2 Days)

Yeh wo cheezein hain jo **bina koi naya indicator banaye** abhi current pipeline ko zyada reliable banayegi.

#### 1.1 Test Coverage Add Karein
**File:** `tests/` (naya folder)
**Kya:** Indicators (EMA, RSI, ATR, ADX) ke unit tests jo MT5 reference values se compare karein
**Why:** Abhi indicator correctness sirf "claim" hai. Refactor karne pe silent breakage ho sakta hai.
**Impact:** ⭐⭐⭐ (reliability, regression safety)

#### 1.2 Acceptance Gate Configurable Banao
**File:** `run_validation.py` line ~92
**Problem:** PF=1.10, DD=15%, trades=100 sab hard-coded. Different markets (HFT vs swing) alag thresholds chahte hain.
**Fix:** `config/gates.yaml` se threshold load karein
**Impact:** ⭐⭐ (flexibility per asset class)

#### 1.3 Spread/Commission Per-Symbol Configurable
**File:** `run_validation.py::engine_factory_kwargs()`
**Problem:** XAUUSD ke values hard-coded (`commission_per_lot=7.0, slippage_points=10.0`). EURUSD, BTCUSD ke liye different chahiye.
**Fix:** `config/symbols.yaml` se per-symbol load
**Impact:** ⭐⭐⭐ (multi-asset reliability)

#### 1.4 GA Hyperparameters Configurable + Stronger Default
**File:** `run_validation.py` lines ~140
**Current:** `pop=20, gens=15` (~300 evals)
**CLAUDE.md spec:** `pop ≤ 50, gens ≤ 100` (~5000 evals)
**Fix:** `--depth=quick|standard|deep` flag add karo
**Impact:** ⭐⭐⭐ (deep mode mein optimization quality bahut behtar)

#### 1.5 News Calendar Filter
**File:** `validation/news_filter.py` (naya)
**Kya:** ForexFactory ya Investing.com calendar API se high-impact news (NFP, FOMC, CPI) ke 30 min before/after sab trades skip karein
**Why:** Backtest mein news periods ke wild moves edge ko inflate kar sakte hain — live mein woh edge fake hoti hai.
**Impact:** ⭐⭐⭐⭐ (real-world reliability major boost)

#### 1.6 Equity Curve Stationarity Test
**File:** `validation/stationarity.py` (naya)
**Math:** Augmented Dickey-Fuller test on equity curve returns
**Why:** Agar equity returns non-stationary hain (mean drift kar raha hai), strategy decay ho rahi hai. Catch kar lo.
**Impact:** ⭐⭐⭐ (detect strategy "death")

---

### LEVEL 2 — New Strategy Templates (Real Edge Candidates, 3-5 Days)

Yeh wo strategies hain jo academic literature mein **prove ho chuki hain edge dene wali**, par retail crowds nahi use karte:

#### 2.1 Pairs Trading / Statistical Arbitrage
**File:** `skills/pairs_template.py` (naya)
**Math:** Cointegration test (Engle-Granger), z-score on spread, mean-reversion entry
**Why edge:** XAU vs XAG, EURUSD vs GBPUSD jaise correlated pairs mein spread mean-reverts. Yeh classic "stat arb" hai.
**Risk:** Cointegration breakdown — z-score 4σ pe bhi reverse nahi hota. Stop-out logic chahiye.

#### 2.2 Volatility Regime Switching
**File:** `skills/volregime_template.py` (naya)
**Math:** GARCH(1,1) for volatility forecasting, regime switch when vol crosses threshold
**Why edge:** Same strategy alag-alag vol regimes mein alag perform karti hai. Trend strategies low-vol mein die karte hain, mean-rev high-vol mein die karte hain. Regime se gating add karo.

#### 2.3 Order Flow Imbalance (OFI) Strategy
**File:** `skills/orderflow_template.py` (naya)
**Math:** Tick-data se buy-volume vs sell-volume aggregated per bar, normalised by total volume
**Why edge:** Real-time microstructure signal jo daily/M15 close pe nahi dikhta. Most retail isse access nahi karte (tick data zaroori hai).
**Limitation:** MT5 tick data zaroori hai (M5 OHLC se nahi banta). Architecture change chahiye.

#### 2.4 Volume Profile Mean Reversion
**File:** `skills/volprofile_template.py` (naya)
**Math:** Rolling Volume Point of Control (VPOC), value area high/low. Entry on extreme deviations.
**Why edge:** Institutions ke positioning ka proxy. Standard MA-based strategies se orthogonal signal.

#### 2.5 Cross-Asset Carry / Correlation Strategy
**File:** `skills/crossasset_template.py` (naya)
**Math:** XAUUSD aur DXY (dollar index) ki rolling correlation. Divergence pe trade.
**Why edge:** Multi-symbol context. Single-asset traders yeh dekh hi nahi paate.
**Limitation:** Multi-symbol data loader chahiye (abhi single CSV pe hai).

---

### LEVEL 3 — AI-Built Custom Indicators (Real Innovation, 1-2 Weeks)

**Yahan se asli answer aata hai user ke sawaal ka.**

---

## Part 3 — Custom Indicators: Kya AI Genuinely Build Kar Sakta Hai

### Pehle Disclaimer:
- Yeh "AI ne magic indicator banaya jo profit guarantee karta hai" wala hype nahi hai.
- Yeh **established mathematical/statistical methods** hain jo retail traders aam taur pe nahi use karte.
- Sab indicators ko **rigorous statistical testing** se guzarna padega (no look-ahead, IS/OOS, Monte Carlo).

### 3.1 — Indicators That Are Genuinely Novel (For Retail)

#### Indicator A: **Hurst Exponent (Fractal Memory)**

**Math:** Rescaled Range (R/S) analysis ya DFA (Detrended Fluctuation Analysis)
**Output:** Single value 0 < H < 1
- H ≈ 0.5: Random walk (efficient market)
- H > 0.5: Trending (persistent)
- H < 0.5: Mean-reverting (anti-persistent)

**Why edge:** Bata deta hai ki current market trending hai ya mean-reverting — **before applying** trend or mean-rev strategy. Most strategies regime-blind hote hain, yeh regime-aware bana deta hai.

**Implementation file:** `indicators/hurst.py`
```python
def hurst_exponent(series: pd.Series, lags: range = range(2, 100)) -> float:
    """Returns rolling Hurst exponent. Uses R/S analysis."""
    # ... ~30 lines of code
```

**Statistical foundation:** Mandelbrot's fractal market hypothesis (1960s, well-established).
**Reliability:** ⭐⭐⭐⭐ — academic literature pe well-documented.

---

#### Indicator B: **Sample Entropy / Permutation Entropy**

**Math:** Information theory — kitni "predictable" hai recent price series
**Output:** 0 (highly predictable) → high (random)

**Why edge:** Low entropy = pattern hai = strategy chalegi. High entropy = noise = strategies fail karte hain. **Adaptive position sizing** ke liye perfect — entropy high ho toh size halve karo.

**Implementation file:** `indicators/entropy.py`
```python
def permutation_entropy(series, m=3, tau=1) -> float:
    """Bandt-Pompe permutation entropy."""
```

**Statistical foundation:** Bandt & Pompe (2002) — physics literature mein well-tested.
**Reliability:** ⭐⭐⭐⭐

---

#### Indicator C: **Wavelet Decomposition Trend Strength**

**Math:** Discrete Wavelet Transform (DWT) — price series ko different frequency bands mein decompose karta hai
**Output:** Per-frequency-band energy, dominant timeframe identify karta hai

**Why edge:** Standard EMAs sirf ek timeframe ka view dete hain. Wavelets simultaneously M5, M15, H1, H4, D1 ka decomposed view dete hain — bata dete hain konsi timeframe pe trend dominant hai.

**Implementation file:** `indicators/wavelet.py`
```python
import pywt

def wavelet_trend(close: pd.Series, level: int = 5) -> dict:
    """Returns trend strength per timeframe via Daubechies wavelets."""
```

**Statistical foundation:** Wavelet theory (Daubechies 1988) — solid math.
**Reliability:** ⭐⭐⭐⭐⭐

---

#### Indicator D: **Kalman Filter Adaptive Trend**

**Math:** State-space model jo "true price" estimate karta hai noise se. Adaptive — market change hone pe update hota hai.
**Output:** Smoothed price + velocity (trend speed) + acceleration

**Why edge:** EMA lag karta hai (slow). Kalman zero-lag ke kareeb hota hai aur volatility adapt karta hai automatically.

**Implementation file:** `indicators/kalman.py`
```python
from filterpy.kalman import KalmanFilter

def kalman_trend(close: pd.Series, q: float = 0.001, r: float = 0.1):
    """Adaptive smoothed trend + velocity from Kalman filter."""
```

**Statistical foundation:** Kalman (1960) — radar/aerospace mein 60+ saal se proven.
**Reliability:** ⭐⭐⭐⭐⭐

---

#### Indicator E: **Mahalanobis Distance Anomaly Detector**

**Math:** Multivariate distance metric — current bar (RSI, ATR, volume, range) historical distribution se kitna door hai
**Output:** Single value. High = anomalous bar.

**Why edge:** "This bar is unusual" detector. Pre-news spikes, fake breakouts, rogue volume — sab catch hote hain. Strategies ko gate karke "skip anomalous bars" rule add kar do, false signals reduce.

**Implementation file:** `indicators/mahalanobis.py`

**Statistical foundation:** Mahalanobis (1936) — multivariate stats ka classic.
**Reliability:** ⭐⭐⭐⭐

---

#### Indicator F: **Transfer Entropy Cross-Asset Lead/Lag**

**Math:** Information theory — kitni information XAUUSD ki movement DXY ke past se predict karti hai
**Output:** Per pair lead/lag relationship strength

**Why edge:** XAUUSD H1 mein chalti hai DXY ke 30-min pehle ke move se? Yeh detect karta hai. Confirmation filter banao.

**Statistical foundation:** Schreiber (2000) — physics + finance literature.
**Reliability:** ⭐⭐⭐ (computationally expensive, par genuine edge dikha hai academic studies mein)

---

#### Indicator G: **Hidden Markov Model (HMM) Regime Detector**

**Math:** Probabilistic model jo unobserved "market regimes" (bull/bear/sideways) infer karta hai observed price moves se
**Output:** Probability of being in regime 1, 2, 3 (configurable)

**Why edge:** Hard regime classification ki jagah probabilistic. Smooth transitions, no whipsaw.

**Implementation file:** `indicators/hmm_regime.py`
```python
from hmmlearn import hmm

def hmm_regime_proba(returns: pd.Series, n_regimes: int = 3):
    """Returns regime probability matrix."""
```

**Statistical foundation:** Baum-Welch algorithm (1960s) + Hamilton (1989) for finance.
**Reliability:** ⭐⭐⭐⭐

---

### 3.2 — Indicators That AI Can DESIGN (Original)

Yeh wo cheezein hain jo **literally koi indicator library mein nahi hain**, par kaam karne ka mathematical reason hai:

#### Custom A: **Multi-Resolution Fractal Confluence Score**

**Idea:** Hurst exponent ko 5 timeframes (M5, M15, H1, H4, D1) pe rolling-compute karo. Jab sab 5 timeframes pe H > 0.6 (sab trending), strong trend signal. Sab pe H < 0.4, strong mean-reversion. Mixed = no trade.

**Why custom:** Yeh combination kahin pre-existing nahi hai. Real edge hai kyunki most traders single-TF dekhte hain, multi-TF fractal coherence rare aur powerful confluence hai.

---

#### Custom B: **Liquidity-Weighted Price Pressure**

**Idea:** Volume Profile + Order Flow + Time-of-Day weighted. Bata deta hai current price level pe "pressure" build hua hai ki nahi. Standard VPOC se zyada nuanced.

**Math:** `pressure[t] = Σ(vol_i × time_decay × proximity_to_price) for i in last_N_bars`

---

#### Custom C: **Adaptive Regime-Vol Composite (ARVC)**

**Idea:** Hurst (regime) + GARCH (vol forecast) + Sample Entropy (predictability) ko ek single 0-100 score mein combine. Score > 70 = chalo trade. Score < 30 = sit out.

**Why custom:** Yeh meta-indicator hai. AI design kar sakta hai ki teen signals ko optimal weighting kaise mile (linear regression ya neural net se).

---

#### Custom D: **Microstructure Noise Filter**

**Idea:** Kalman + wavelet denoising combine karke "true" price extract karo. Indicators isi denoised series pe compute karo. False signals automatic filter ho jayenge.

---

### 3.3 — Workflow: Custom Indicator Develop Karne Ka

Har naya indicator iss pipeline se guzrega:

```
Step 1: Mathematical formulation
  ├── Statistical foundation document karo
  ├── No-lookahead proof likhna mandatory
  └── Computational complexity check (real-time feasible?)

Step 2: Implement in indicators/<name>.py
  ├── Vectorised pandas/numpy
  ├── Deterministic
  └── Unit tests with synthetic + known-output cases

Step 3: Wrap as a Strategy template in skills/
  ├── Use indicator as primary signal
  ├── ATR-based SL/TP
  └── 5-7 free params for GA

Step 4: Run through full validation pipeline
  ├── IS optimise
  ├── OOS test
  ├── Walk-forward (5 windows)
  ├── Monte Carlo (1000 runs)
  └── Acceptance gate

Step 5: If pass → MQ5/Pine export → demo forward 4-8 weeks
       If fail → archive learnings, no fitting
```

**Critical rule:** Naya indicator banane ka matlab pipeline relax karna nahi. Same strict gates har candidate ke liye.

---

## Part 4 — Realistic Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Test framework setup (`pytest` + indicator unit tests)
- [ ] Configurable acceptance gates (`config/gates.yaml`)
- [ ] Per-symbol cost configs (`config/symbols.yaml`)
- [ ] News filter integration
- [ ] GA depth flag (`--depth=deep`)

**Outcome:** App reliable ban gayi, bugs catch hote hain, multi-asset support strong hai.

### Phase 2: Existing-Math Indicators (Week 2)
- [ ] `indicators/hurst.py` (R/S analysis)
- [ ] `indicators/entropy.py` (sample + permutation)
- [ ] `indicators/kalman.py` (adaptive trend)
- [ ] `indicators/wavelet.py` (multi-resolution)
- [ ] Each + corresponding `skills/<name>_template.py`

**Outcome:** 4 naye indicators, 4 nayi strategies — genuinely different from RSI/MA/MACD.

### Phase 3: AI-Designed Composites (Week 3)
- [ ] `indicators/fractal_confluence.py` (multi-TF Hurst combine)
- [ ] `indicators/arvc.py` (adaptive regime-vol composite)
- [ ] `indicators/hmm_regime.py` (probabilistic regime)
- [ ] Strategy templates using composites

**Outcome:** App ke pass apne unique edge candidates hain — pure CLAUDE.md ke 5 strategies se aage.

### Phase 4: Validation Round (Week 4)
- [ ] Saare new indicators pe full pipeline run
- [ ] Multi-symbol (XAU, EUR, GBP, BTC)
- [ ] Multiple timeframes (M5, M15, H1)
- [ ] Best 2-3 candidates demo forward 4-8 weeks

**Outcome:** Empirical evidence kaun-sa indicator + strategy combo genuinely edge deta hai.

---

## Part 5 — Honest Expectations

### Kya hoga Phase 4 ke baad:

| Optimistic case (~25% chance) | Realistic case (~50%) | Pessimistic case (~25%) |
|---|---|---|
| 1-2 strategies VALIDATED, demo bhi pass | Sab fail, par valuable insights mile | Saari strategies overfit nikli |
| Live deploy candidate ready | Pipeline mature ho gayi for round 2 | Custom indicators standard se better nahi nikle |
| Edge real hai, scaling possible | More research zaroori | Restart with different markets |

**Sab cases mein win:** Tum apne pass ek **rigorous, custom, multi-indicator backtest framework** ban jaayega — jisko tum future ideas pe apply kar sakte ho. Yeh tool "ek strategy" tak limited nahi rahega, ek **strategy R&D platform** ban jaayega.

---

## Part 6 — Final Honest Verdict

### Kya yeh roadmap profit guarantee karta hai?
**Nahi.** Koi roadmap nahi karta.

### Kya yeh roadmap profit ka chance badhata hai?
**Haan, significantly.** Reasons:
1. Custom indicators = signal-to-noise ratio better (kam crowded)
2. Multi-asset, multi-TF = diversification
3. Regime-aware strategies = drawdown control
4. Statistical rigor = false positives kam
5. News filter = backtest-live gap kam

### AI khud naya indicator bana sakta hai?
**Haan — par "AI-magic" nahi.** AI:
- Existing math (Hurst, Kalman, wavelets, HMM, entropy) ko trading mein apply kar sakti hai (90% retail nahi karte)
- Multiple indicators ko optimal weighting/combination mein wrap kar sakti hai (composite indicators)
- Synthetic data pe new formulas test kar sakti hai
- Genetic programming se literally naye indicator formulas evolve kar sakti hai (advanced — Phase 5+)

**Lekin:** "Naya formula" nahi banta hai jo physics ke laws tod de — math finite hai. Edge aati hai **application + validation + execution** se, sirf formula se nahi.

---

## Part 7 — Next Step

**Tumhara call hai:**

**Option A — Conservative:** Sirf Phase 1 + Phase 2 (Levels 1-2). 2 hafte mein pipeline strong + 4 naye indicators. Production-ready system.

**Option B — Aggressive:** Saare 4 phases. 1 mahina. Apna unique edge research platform.

**Option C — Custom:** Specific items pick karo niche se. Mujhe bolo, exact estimates de doonga.

**Recommendation:** **Option A pehle**, agar Phase 2 mein koi 1 strategy genuine VALIDATED ho jaaye (gates + demo dono pe), tab Phase 3 mein invest karo. Iss tarah resources waste nahi hote agar foundation hi weak ho.

---

*Yeh document `OPTIMIZATION_AND_CUSTOM_INDICATORS.md` ke naam se root folder mein save hua hai. Codebase ka koi file modify nahi hua. Yeh planning + research direction document hai — agar tum bole "Phase 1 start karo" toh actual implementation alag commits mein hogi.*
