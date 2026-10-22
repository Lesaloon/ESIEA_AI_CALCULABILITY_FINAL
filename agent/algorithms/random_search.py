"""Random search over the weighted A* parameter w."""

import random
from math import isfinite
from time import perf_counter

from agent.algorithms.grid_search import _path_cost, _score
from agent.algorithms.weighted_astar import WeightedAStar


def random_search(graph, start, target, heuristic='l1', low=1, high=50, count=10, seed=None):
    """Try `count` random values of w drawn uniformly in [low, high].

    Bounds must be finite and at least 1. The default draw is 10 values in
    [1, 50]. There is no step. The best w uses the same cost/duration score
    as the grid search.
    """
    trials = []
    for w in _samples(low, high, count, seed):
        algorithm = WeightedAStar(heuristic, w)
        started = perf_counter()
        result = algorithm.search(graph, start, target)
        duration = perf_counter() - started
        trials.append(dict(
            w=w,
            cost=_path_cost(graph, result.path),
            duration=duration,
            expansions=len(result.trace.expanded),
            path=result.path,
        ))

    best_cost = min(trial['cost'] for trial in trials)
    best_duration = min(trial['duration'] for trial in trials)
    for trial in trials:
        trial['score'] = _score(trial, best_cost, best_duration)
    best = min(trials, key=lambda trial: (trial['score'], trial['w']))
    return dict(best=best, trials=trials)


def _samples(low, high, count, seed):
    low, high = float(low), float(high)
    if not isfinite(low) or not isfinite(high):
        raise ValueError('bounds must be finite')
    if low < 1 or high < 1:
        raise ValueError('bounds must belong to [1, +inf]')
    if low > high:
        raise ValueError('low must be lower than or equal to high')
    if type(count) is not int or count < 1:
        raise ValueError('count must be a positive integer')
    picker = random.Random(seed)
    return [picker.uniform(low, high) for _ in range(count)]
