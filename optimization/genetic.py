"""genetic.py — generic genetic algorithm over a strategy's parameter space.

Pass:
  - a callable `eval_fn(params: dict) -> float` (fitness, higher is better)
  - a list of ParamSpec describing the search ranges
  - GA hyperparameters

Returns: best (params, fitness) and a generation history.
Deterministic given seed.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any
import random
import numpy as np


@dataclass
class ParamSpec:
    name: str
    low: float
    high: float
    type: str = "float"      # "float" | "int"
    step: float | None = None

    def sample(self, rng: random.Random) -> Any:
        if self.type == "int":
            return rng.randint(int(self.low), int(self.high))
        v = rng.uniform(self.low, self.high)
        if self.step:
            v = round(v / self.step) * self.step
        return float(v)

    def mutate(self, value, rng: random.Random, sigma: float = 0.1):
        span = self.high - self.low
        v = value + rng.gauss(0, sigma * span)
        v = max(self.low, min(self.high, v))
        if self.type == "int":
            return int(round(v))
        if self.step:
            v = round(v / self.step) * self.step
        return float(v)


class GeneticOptimizer:
    def __init__(
        self,
        param_specs: list[ParamSpec],
        eval_fn: Callable[[dict], float],
        population: int = 30,
        generations: int = 30,
        elite_frac: float = 0.2,
        mutation_rate: float = 0.25,
        crossover_rate: float = 0.7,
        seed: int = 42,
    ):
        self.specs = param_specs
        self.eval_fn = eval_fn
        self.population = population
        self.generations = generations
        self.elite_n = max(1, int(population * elite_frac))
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.rng = random.Random(seed)

    # -------------------------------------------------------- helpers
    def _random_individual(self) -> dict:
        return {s.name: s.sample(self.rng) for s in self.specs}

    def _crossover(self, a: dict, b: dict) -> dict:
        child = {}
        for s in self.specs:
            child[s.name] = a[s.name] if self.rng.random() < 0.5 else b[s.name]
        return child

    def _mutate(self, ind: dict) -> dict:
        out = dict(ind)
        for s in self.specs:
            if self.rng.random() < self.mutation_rate:
                out[s.name] = s.mutate(out[s.name], self.rng)
        return out

    # ----------------------------------------------------------- run
    def run(self, verbose: bool = False) -> dict:
        pop = [self._random_individual() for _ in range(self.population)]
        scores = [self.eval_fn(ind) for ind in pop]
        history = []

        for g in range(self.generations):
            # rank by fitness desc
            order = np.argsort(scores)[::-1]
            pop = [pop[i] for i in order]
            scores = [scores[i] for i in order]
            best = pop[0]; best_score = scores[0]
            history.append({"gen": g, "best": best_score, "mean": float(np.mean(scores))})
            if verbose:
                print(f"  gen {g:02d}  best={best_score:.4f}  mean={np.mean(scores):.4f}")

            # next generation: elitism + crossover + mutation
            new_pop = pop[: self.elite_n]
            while len(new_pop) < self.population:
                if self.rng.random() < self.crossover_rate:
                    p1 = self.rng.choice(pop[: self.elite_n * 3])
                    p2 = self.rng.choice(pop[: self.elite_n * 3])
                    child = self._crossover(p1, p2)
                else:
                    child = dict(self.rng.choice(pop[: self.elite_n * 3]))
                child = self._mutate(child)
                new_pop.append(child)

            pop = new_pop
            scores = [self.eval_fn(ind) for ind in pop]

        # final ranking
        order = np.argsort(scores)[::-1]
        return {
            "best_params": pop[order[0]],
            "best_score": float(scores[order[0]]),
            "history": history,
        }
