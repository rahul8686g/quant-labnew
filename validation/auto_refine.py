"""auto_refine.py — disciplined multi-attempt validation wrapper.

Calls the main validation pipeline up to N times. After each rejection it
inspects the failure pattern and proposes ONE architectural refinement
(timeframe, session window, or strategy-family focus). Refinements are
DATA-DRIVEN — never random parameter tweaks.

Hard rules (never relaxed):
  * Acceptance gates stay identical every attempt.
  * OOS data split stays identical every attempt.
  * Max 3 attempts. After that, final verdict is NO_EDGE.
  * Each attempt's full report is preserved in its own folder.
"""
from __future__ import annotations
from collections import Counter
from typing import Callable


# ----------------------------------------------------------- analyse failure
def _failure_signature(candidates: list[dict]) -> dict:
    """Count which gates failed across all candidates → drives refinement choice."""
    bucket: Counter[str] = Counter()
    for c in candidates:
        for r in c.get("reasons", []):
            r_low = r.lower()
            if "trades" in r_low and "< 100" in r:
                bucket["low_trades"] += 1
            elif "overfit" in r_low or "is/oos" in r_low:
                bucket["overfit"] += 1
            elif "pf" in r_low and "<= 1.10" in r:
                bucket["weak_pf"] += 1
            elif "dd" in r_low and ">= 15" in r:
                bucket["high_dd"] += 1
            elif "mc" in r_low and "<= start" in r:
                bucket["mc_fail"] += 1
            elif "wf" in r_low or "windows profitable" in r_low:
                bucket["wf_unstable"] += 1
            else:
                bucket["other"] += 1
    return dict(bucket)


# --------------------------------------------------------- propose refinement
def propose_refinement(prev_attempt: dict, attempt_num: int) -> dict:
    """Inspect the previous attempt's verdict and return a config override
    dict for the next attempt. Returns {} if no meaningful refinement
    possible — caller should stop in that case.
    """
    candidates = prev_attempt.get("candidates", [])
    if not candidates:
        return {}
    sig = _failure_signature(candidates)

    # rank failure modes by frequency
    if not sig:
        return {}
    top_mode = max(sig.items(), key=lambda kv: kv[1])[0]

    # ---- mode → architectural change (only ONE change per attempt) ----
    if top_mode == "overfit":
        # too aggressive optimisation → step up to a less-noisy TF
        return {
            "exec_tf": "30min",
            "_reason": "Many candidates overfit (IS strong, OOS weak). "
                       "Stepping to M30 to reduce noise & curve-fit risk.",
        }
    if top_mode == "weak_pf":
        # filters didn't separate signal from noise — focus on the family
        # that came closest to the threshold (highest OOS PF)
        best = max(candidates, key=lambda c: c.get("oos_pf", 0.0))
        return {
            "only_family": best.get("name"),
            "_reason": f"All candidates had weak PF; focusing exclusively on "
                       f"the best-performing family ({best.get('name')}, "
                       f"OOS PF {best.get('oos_pf')}).",
        }
    if top_mode == "low_trades":
        # filters too tight — narrow to the most active sessions
        return {
            "sessions": ["london", "newyork"],
            "_reason": "Too few OOS trades; concentrating on LDN+NY sessions "
                       "(higher activity than Asian).",
        }
    if top_mode == "high_dd":
        # risk too high — tighter sizing for next attempt
        return {
            "risk_pct": 0.25,
            "_reason": "OOS drawdown exceeded 15%; halving risk per trade to 0.25%.",
        }
    if top_mode == "mc_fail":
        # equity sequence luck-dependent → step up TF for cleaner trades
        return {
            "exec_tf": "1H",
            "_reason": "Monte Carlo p5 below start (sequence-dependent results). "
                       "Stepping to H1 for fewer, higher-quality trades.",
        }
    if top_mode == "wf_unstable":
        # walk-forward unstable → focus on most-robust family
        # use the one with most profitable WF windows from prev candidates
        best = max(candidates, key=lambda c: c.get("oos_pf", 0.0))
        return {
            "only_family": best.get("name"),
            "_reason": f"Walk-forward unstable across all candidates; "
                       f"focusing on {best.get('name')} which was closest.",
        }
    return {}   # unknown failure mode — let caller stop


# ---------------------------------------------------------------- main loop
def auto_refine_validate(
    runner: Callable[..., dict],
    base_kwargs: dict,
    max_attempts: int = 3,
    log: Callable[[str], None] | None = None,
) -> dict:
    """Run `runner(**base_kwargs)` up to `max_attempts` times, applying a
    data-driven refinement override between attempts. Returns a combined
    verdict with all attempts preserved.

    runner    : a callable that accepts kwargs and returns a verdict dict
                shaped like run_validation.main(). Must include
                'verdict', 'candidates', and (if VALIDATED) 'winner'.
    base_kwargs: kwargs for the FIRST attempt.
    """
    def _say(msg: str):
        if log: log(msg)

    attempts = []
    current_kwargs = dict(base_kwargs)
    current_kwargs["_attempt"] = 1
    current_kwargs["_refine_reason"] = "baseline (user-provided INFO)"

    for n in range(1, max_attempts + 1):
        _say(f"\n========== ATTEMPT {n} / {max_attempts} ==========")
        _say(f"refinement: {current_kwargs.get('_refine_reason', '—')}")
        result = runner(**{k: v for k, v in current_kwargs.items()
                           if not k.startswith("_")})
        attempts.append({
            "attempt":   n,
            "refinement": current_kwargs.get("_refine_reason"),
            "config":    {k: v for k, v in current_kwargs.items() if not k.startswith("_")},
            "verdict":   result.get("verdict"),
            "winner":    result.get("winner"),
            "summary":   [{"name": c["name"], "passed": c.get("passed", False),
                           "oos_pf": c.get("oos_pf"), "reasons": c.get("reasons", [])}
                          for c in result.get("candidates", [])],
            "run_dir":   result.get("run_dir"),
        })
        if result.get("verdict") == "VALIDATED":
            _say(f"=> ATTEMPT {n} PASSED. Stopping early.")
            return _finalize(attempts, result, "VALIDATED")

        # rejected — propose a refinement for the next attempt
        if n == max_attempts:
            _say(f"=> All {max_attempts} attempts rejected. Stopping.")
            break
        ref = propose_refinement(result, n + 1)
        if not ref:
            _say("=> No data-driven refinement applicable. Stopping early.")
            break
        _say(f"=> rejected. Proposed for attempt {n+1}: {ref}")
        current_kwargs = {**base_kwargs, **ref, "_attempt": n + 1}

    return _finalize(attempts, result, "NO_EDGE")


def _finalize(attempts: list[dict], last_result: dict, final_verdict: str) -> dict:
    return {
        "final_verdict":  final_verdict,
        "attempts_run":   len(attempts),
        "attempts":       attempts,
        "winner":         last_result.get("winner") if final_verdict == "VALIDATED" else None,
        "last_run_dir":   last_result.get("run_dir"),
    }
