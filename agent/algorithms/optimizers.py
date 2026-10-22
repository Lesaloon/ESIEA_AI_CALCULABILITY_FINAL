"""Parameter optimizers that tune weighted A* on the frozen map.

An optimizer looks for the (heuristic, weight) pair with the lowest score

    score = cost_weight * cost/cost_ref + time_weight * time/time_ref + memory_weight * memory/memory_ref

where cost is the route cost, time the search duration and memory the peak memory
allocated by the search. Each criterion is divided by the same measure for the
reference search (classic A*, L-infinity, weight 1), so a ratio of 1 means
"as good as the reference" and criteria of different units can be mixed.
Each evaluation is a full A* search on the known graph (no physical move).
"""

import random
import tracemalloc
from dataclasses import dataclass
from itertools import product
from math import inf
from time import perf_counter

from agent.algorithms.astar import AStar

HEURISTICS = ('l1', 'l2', 'linf', 'squared_l2', 'mse')
REFERENCE = ('linf', 1.0)
TIMING_REPEATS = 3


@dataclass(frozen=True)
class Param:
    id: str
    label: str
    default: float
    min: float
    max: float
    step: float
    boolean: bool = False  # 0/1 flag, shown as a checkbox
    group: str = 'Search space'  # The UI shows parameters of one group in one block


CRITERIA = (Param('cost_weight', 'Cost importance', 1, 0, 10, 0.1, group='Scoring importance'),
            Param('time_weight', 'Time importance', 1, 0, 10, 0.1, group='Scoring importance'),
            Param('memory_weight', 'Memory importance', 1, 0, 10, 0.1, group='Scoring importance'))
LOCK = Param('lock_heuristic', 'Lock the heuristic (tune only the weight)', 0, 0, 1, 1,
             boolean=True, group='Heuristic')


def path_cost(graph, path):
    return sum(graph.edges[a][b] for a, b in zip(path, path[1:]))


def measure(graph, start, target, heuristic, weight):
    """Run one A* search and return (path, time_ms, memory_kb, expanded)."""
    search = AStar(heuristic, weight).search
    times = []
    for _ in range(TIMING_REPEATS):  # best of N: robust against scheduling noise
        began = perf_counter()
        search(graph, start, target, trace=False)
        times.append((perf_counter() - began) * 1000)
    tracing = tracemalloc.is_tracing()
    if not tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    baseline = tracemalloc.get_traced_memory()[0]
    result = search(graph, start, target, trace=False)
    peak = tracemalloc.get_traced_memory()[1] - baseline
    if not tracing:
        tracemalloc.stop()
    return result.path, min(times), peak / 1024, len(result.trace.expanded)


class Evaluator:
    """Score (heuristic, weight) pairs and keep every distinct trial."""

    def __init__(self, graph, start, target, importance):
        self.graph, self.start, self.target, self.importance = graph, start, target, importance
        self.trials = []
        self._cache = {}
        path, time_ms, memory_kb, _ = measure(graph, start, target, *REFERENCE)
        self.reference = dict(heuristic=REFERENCE[0], weight=REFERENCE[1],
                              cost=path_cost(graph, path) if path else None,
                              time_ms=time_ms, memory_kb=memory_kb)
        # max() avoids dividing by zero on trivial maps (start == goal, unreachable goal)
        self._scale = dict(cost=max(self.reference['cost'] or 0, 1e-9), time_ms=max(time_ms, 1e-6),
                           memory_kb=max(memory_kb, 1e-6))

    def __call__(self, heuristic, weight):
        key = heuristic, round(weight, 3)
        if key not in self._cache:
            path, time_ms, memory_kb, expanded = measure(self.graph, self.start, self.target, *key)
            found = bool(path)
            cost = path_cost(self.graph, path) if found else None
            score = (self.importance['cost_weight'] * cost / self._scale['cost']
                     + self.importance['time_weight'] * time_ms / self._scale['time_ms']
                     + self.importance['memory_weight'] * memory_kb / self._scale['memory_kb']) if found else inf
            self._cache[key] = score
            self.trials.append(dict(heuristic=heuristic, weight=key[1], found=found, cost=cost,
                                    time_ms=time_ms, memory_kb=memory_kb, expanded=expanded,
                                    score=score if found else None))
        return self._cache[key]


class Optimizer:
    label = ''
    description = ''
    params: tuple[Param, ...] = (LOCK, *CRITERIA)
    uses_start = False  # True when the heuristic and weight of the run configuration are a starting point

    def __init__(self, values=None):
        self.values = self.resolve(values or {})

    @classmethod
    def resolve(cls, given):
        """Fill defaults and validate; raises ValueError on unknown or out-of-range values."""
        known = {p.id: p for p in cls.params}
        unknown = set(given) - set(known)
        if unknown:
            raise ValueError(f'Unknown parameter: {", ".join(sorted(unknown))}')
        values = {}
        for param in cls.params:
            value = given.get(param.id, param.default)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not param.min <= value <= param.max:
                raise ValueError(f'{param.label} must be between {param.min} and {param.max}')
            values[param.id] = value
        if not any(values[p.id] for p in CRITERIA):
            raise ValueError('At least one importance must be above zero')
        if values[LOCK.id] not in (0, 1):
            raise ValueError('Lock heuristic must be 0 or 1')
        cls.validate(values)
        return values

    @classmethod
    def validate(cls, values):
        pass

    def tune(self, graph, start, target, heuristic, weight):
        """Return (best_heuristic, best_weight, trials, reference)."""
        evaluate = Evaluator(graph, start, target, self.values)
        start = heuristic if self.values[LOCK.id] or heuristic in HEURISTICS else 'l1'
        best = self.optimize(evaluate, start, weight)
        return best[0], best[1], evaluate.trials, evaluate.reference

    def heuristics(self, selected):
        """Heuristics the search may use: only the selected one when locked."""
        return (selected,) if self.values[LOCK.id] else HEURISTICS

    def optimize(self, evaluate, heuristic, weight):
        raise NotImplementedError

    @staticmethod
    def best_of(evaluate, candidates):
        # min() keeps the first of equal scores, so results are deterministic.
        return min(candidates, key=lambda c: evaluate(*c))


class GridSearch(Optimizer):
    label = 'Grid search'
    description = 'Tries every heuristic with every weight from min to max in fixed steps.'
    params = (LOCK,
              Param('weight_min', 'Weight min', 1, 1, 20, 0.1),
              Param('weight_max', 'Weight max', 3, 1, 20, 0.1),
              Param('weight_step', 'Weight step', 0.5, 0.1, 5, 0.1),
              *CRITERIA)

    @classmethod
    def validate(cls, v):
        if v['weight_min'] > v['weight_max']:
            raise ValueError('Weight min must not exceed weight max')
        if (v['weight_max'] - v['weight_min']) / v['weight_step'] > 40:
            raise ValueError('Grid too large: use at most 41 weights')

    def optimize(self, evaluate, heuristic, weight):
        v = self.values
        count = int((v['weight_max'] - v['weight_min']) / v['weight_step'] + 1e-9)
        weights = [round(v['weight_min'] + i * v['weight_step'], 3) for i in range(count + 1)]
        return self.best_of(evaluate, product(self.heuristics(heuristic), weights))


class RandomSearch(Optimizer):
    label = 'Random search'
    description = 'Samples random (heuristic, weight) pairs and keeps the best one.'
    params = (LOCK,
              Param('trials', 'Trials', 20, 1, 200, 1),
              Param('weight_min', 'Weight min', 1, 1, 20, 0.1),
              Param('weight_max', 'Weight max', 5, 1, 20, 0.1),
              Param('seed', 'Seed', 42, 0, 1_000_000, 1),
              *CRITERIA)

    @classmethod
    def validate(cls, v):
        if v['weight_min'] > v['weight_max']:
            raise ValueError('Weight min must not exceed weight max')

    def optimize(self, evaluate, heuristic, weight):
        v = self.values
        rng = random.Random(int(v['seed']))
        pool = self.heuristics(heuristic)
        # Rounding to one decimal can step outside the bounds, hence the clamp.
        candidates = [(rng.choice(pool), min(max(round(rng.uniform(v['weight_min'], v['weight_max']), 1),
                                                 v['weight_min']), v['weight_max']))
                      for _ in range(int(v['trials']))]
        return self.best_of(evaluate, candidates)


class HillClimbing(Optimizer):
    label = 'Hill climbing'
    description = ('Starts from the chosen heuristic and weight, then repeatedly moves to the best '
                   'neighbor (weight ± step, or another heuristic) until none improves.')
    uses_start = True
    params = (LOCK,
              Param('weight_min', 'Weight min', 1, 1, 20, 0.1),
              Param('weight_max', 'Weight max', 5, 1, 20, 0.1),
              Param('step', 'Weight step', 0.5, 0.1, 5, 0.1),
              Param('max_iterations', 'Max iterations', 20, 1, 100, 1),
              *CRITERIA)

    @classmethod
    def validate(cls, v):
        if v['weight_min'] > v['weight_max']:
            raise ValueError('Weight min must not exceed weight max')

    def optimize(self, evaluate, heuristic, weight):
        v = self.values
        low, high = v['weight_min'], v['weight_max']
        current = heuristic, min(max(weight, low), high)
        evaluate(*current)
        for _ in range(int(v['max_iterations'])):
            h, w = current
            neighbors = [(h, min(max(round(w + d, 3), low), high)) for d in (-v['step'], v['step'])]
            neighbors += [(other, w) for other in self.heuristics(heuristic) if other != h]
            best = self.best_of(evaluate, neighbors)
            if evaluate(*best) >= evaluate(*current):
                break
            current = best
        return current


def local_neighbors(optimizer, current, low, high, step):
    """Neighbors of (heuristic, weight): weight ± step inside the range, or another heuristic."""
    h, w = current
    neighbors = [(h, min(max(round(w + d, 3), low), high)) for d in (-step, step)]
    neighbors += [(other, w) for other in optimizer.heuristics(optimizer.start_heuristic) if other != h]
    return [n for n in dict.fromkeys(neighbors) if n != (h, round(w, 3))]


class SimulatedAnnealing(Optimizer):
    label = 'Simulated annealing'
    description = ('Hill climbing with controlled randomness: at each step a random number e in [0, 1] is drawn; '
                   'if e <= temperature it moves to a random neighbor (even a worse one), otherwise to the best '
                   'neighbor when it improves. The temperature decreases at each iteration, and the best point '
                   'ever seen is kept. Randomness lets it leave a local optimum.')
    uses_start = True
    params = (LOCK,
              Param('weight_min', 'Weight min', 1, 1, 20, 0.1),
              Param('weight_max', 'Weight max', 5, 1, 20, 0.1),
              Param('step', 'Weight step', 0.5, 0.1, 5, 0.1),
              Param('max_iterations', 'Iterations', 30, 1, 200, 1),
              Param('temperature', 'Initial temperature', 1, 0, 1, 0.05, group='Annealing'),
              Param('cooling', 'Cooling factor', 0.9, 0.5, 1, 0.01, group='Annealing'),
              Param('seed', 'Seed', 42, 0, 1_000_000, 1, group='Annealing'),
              *CRITERIA)

    @classmethod
    def validate(cls, v):
        if v['weight_min'] > v['weight_max']:
            raise ValueError('Weight min must not exceed weight max')

    def optimize(self, evaluate, heuristic, weight):
        v = self.values
        low, high = v['weight_min'], v['weight_max']
        rng = random.Random(int(v['seed']))
        self.start_heuristic = heuristic
        current = heuristic, round(min(max(weight, low), high), 3)
        best = current
        for k in range(int(v['max_iterations'])):
            temperature = v['temperature'] * v['cooling'] ** k
            neighbors = local_neighbors(self, current, low, high, v['step'])
            if not neighbors:
                break
            if rng.random() <= temperature:
                current = rng.choice(neighbors)          # exploration: accepted even if worse
            else:
                candidate = self.best_of(evaluate, neighbors)
                if evaluate(*candidate) < evaluate(*current):
                    current = candidate                  # exploitation: hill-climbing move
            if evaluate(*current) < evaluate(*best):
                best = current
        evaluate(*best)
        return best


class TabuSearch(Optimizer):
    label = 'Tabu search'
    description = ('Hill climbing with memory: a tested (heuristic, weight) can never be tested again. It always '
                   'moves to the best non-tabu neighbor, even a worse one, so it cannot cycle and is pushed out '
                   'of local optima. The best point ever seen is kept.')
    uses_start = True
    params = (LOCK,
              Param('weight_min', 'Weight min', 1, 1, 20, 0.1),
              Param('weight_max', 'Weight max', 5, 1, 20, 0.1),
              Param('step', 'Weight step', 0.5, 0.1, 5, 0.1),
              Param('max_iterations', 'Iterations', 20, 1, 200, 1),
              *CRITERIA)

    @classmethod
    def validate(cls, v):
        if v['weight_min'] > v['weight_max']:
            raise ValueError('Weight min must not exceed weight max')

    def optimize(self, evaluate, heuristic, weight):
        v = self.values
        low, high = v['weight_min'], v['weight_max']
        self.start_heuristic = heuristic
        current = heuristic, round(min(max(weight, low), high), 3)
        best = current
        tabu = {current}
        evaluate(*current)
        for _ in range(int(v['max_iterations'])):
            allowed = [n for n in local_neighbors(self, current, low, high, v['step']) if n not in tabu]
            if not allowed:
                break                                    # every neighbor already tested
            current = self.best_of(evaluate, allowed)    # may be worse than the current point
            tabu.add(current)
            if evaluate(*current) < evaluate(*best):
                best = current
        return best
