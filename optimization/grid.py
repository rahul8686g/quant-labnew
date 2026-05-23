"""grid.py — exhaustive grid search (use for small param spaces only)."""
from __future__ import annotations
from typing import Callable
from itertools import product
from .genetic import ParamSpec


class GridOptimizer:
    def __init__(self, param_specs: list[ParamSpec], eval_fn: Callable[[dict], float],
                 n_steps: int = 5):
        self.specs = param_specs
        self.eval_fn = eval_fn
        self.n_steps = n_steps

    def _grid(self, spec: ParamSpec):
        if spec.type == "int":
            n = max(2, min(self.n_steps, int(spec.high - spec.low) + 1))
            step = max(1, (spec.high - spec.low) // (n - 1))
            return list(range(int(spec.low), int(spec.high) + 1, int(step)))
        step = (spec.high - spec.low) / (self.n_steps - 1)
        return [round(spec.low + i * step, 6) for i in range(self.n_steps)]

    def run(self, verbose: bool = False) -> dict:
        names = [s.name for s in self.specs]
        grids = [self._grid(s) for s in self.specs]
        best = None
        best_score = float("-inf")
        total = 1
        for g in grids: total *= len(g)
        if verbose: print(f"  grid size: {total} combinations")
        for combo in product(*grids):
            params = dict(zip(names, combo))
            sc = self.eval_fn(params)
            if sc > best_score:
                best_score = sc; best = params
        return {"best_params": best, "best_score": float(best_score), "combinations": total}
