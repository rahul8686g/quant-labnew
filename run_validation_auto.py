"""run_validation_auto.py — disciplined auto-refine wrapper.

Wraps run_validation.main() with the auto_refine loop:
  * Up to 3 attempts.
  * Same strict acceptance gates each attempt (NEVER relaxed).
  * Between attempts, a data-driven refinement is applied (timeframe,
    session, or strategy-family focus). Refinements are deterministic
    based on the failure pattern of the previous attempt.
  * Stops early on first VALIDATED or when no meaningful refinement remains.
  * Stops at attempt 3 regardless — no infinite loop.

Usage:
    python run_validation_auto.py [data_source]

Same data source rules as run_validation.py:
  * existing file path  → read as MT5 CSV
  * otherwise           → treat as Yahoo symbol, auto-download

Final output: a single JSON block with all attempts preserved + the
final verdict (VALIDATED or NO_EDGE).
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_validation
from validation.auto_refine import auto_refine_validate
from validation.cross_source import cross_validate_winner, adjust_verdict


def _infer_yahoo_symbol(csv_path: str | None) -> str | None:
    """Guess the Yahoo ticker from a CSV path or symbol string.
    Returns None if we don't know a Yahoo equivalent."""
    if not csv_path: return "XAUUSD"
    stem = Path(csv_path).stem.upper().split("_")[0]
    # Known mappings (extend in tools/data_loader._YAHOO_ALIAS)
    known = {"XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY",
             "USDINR", "BTCUSD", "ETHUSD", "SPX", "NASDAQ"}
    if stem in known: return stem
    # MCX gold, custom names — Yahoo has no equivalent
    if "MCX" in stem or "NIFTY" in stem or "BANKNIFTY" in stem: return None
    return stem


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else None

    # local log buffer (wrapper-level) for refinement decisions
    log_lines: list[str] = []
    def log(m: str): log_lines.append(m)

    t0 = time.time()
    verdict = auto_refine_validate(
        runner      = run_validation.main,
        base_kwargs = {"csv_path": csv_path},
        max_attempts = 3,
        log = log,
    )

    # ---- NEW: cross-source verification (the real bug fix) ----
    # After a VALIDATED winner is found on primary data, re-run the same
    # winning params on Yahoo's independent feed. Catches data-source overfit.
    if verdict.get("final_verdict") == "VALIDATED" and verdict.get("winner"):
        w = verdict["winner"]
        yahoo_sym = _infer_yahoo_symbol(csv_path)
        if yahoo_sym is None:
            log(f"\n[cross-source] No Yahoo equivalent for '{csv_path}' — skipping.")
            verdict["final_verdict"] = "VALIDATED_NO_CROSSCHECK"
            verdict["warning"] = ("No alternate data source available for this symbol. "
                                  "Single-source validation only. Demo-forward-test mandatory.")
        else:
            # Determine timeframe from the last attempt config or default
            last_cfg = verdict.get("attempts", [{}])[-1].get("config", {})
            tf = last_cfg.get("exec_tf", "M15")
            log(f"\n[cross-source] Re-validating winner on Yahoo:{yahoo_sym} ({tf}) ...")
            try:
                cross = cross_validate_winner(
                    family    = w.get("family", "trend"),
                    params    = w.get("best_params", {}),
                    yahoo_symbol = yahoo_sym,
                    timeframe = tf,
                )
                verdict = adjust_verdict(verdict, cross)
                if cross.get("available"):
                    m = cross["metrics"]
                    log(f"[cross-source] Yahoo result: PF={m['profit_factor']} "
                        f"profit=${m['net_profit']} DD={m['max_dd_pct']}% "
                        f"trades={m['trades']} -> {'PASS' if cross['passed'] else 'FAIL'}")
                log(f"[cross-source] Final verdict: {verdict['final_verdict']}")
            except Exception as e:
                log(f"[cross-source] error: {e}")
                verdict["cross_source"] = {"available": False, "error": str(e)}

    verdict["wrapper_elapsed_sec"] = round(time.time() - t0, 1)

    # write wrapper-level log next to the LAST attempt's run_dir if available
    last_dir = verdict.get("last_run_dir")
    if last_dir:
        Path(last_dir).parent.joinpath("auto_refine.log").write_text(
            "\n".join(log_lines), encoding="utf-8")

    print(json.dumps(verdict, indent=2, default=str))


if __name__ == "__main__":
    main()
