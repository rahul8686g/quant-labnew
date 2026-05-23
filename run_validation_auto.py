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
    verdict["wrapper_elapsed_sec"] = round(time.time() - t0, 1)

    # write wrapper-level log next to the LAST attempt's run_dir if available
    last_dir = verdict.get("last_run_dir")
    if last_dir:
        Path(last_dir).parent.joinpath("auto_refine.log").write_text(
            "\n".join(log_lines), encoding="utf-8")

    print(json.dumps(verdict, indent=2, default=str))


if __name__ == "__main__":
    main()
