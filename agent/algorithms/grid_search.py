"""Manual grid search over the weighted A* parameter w."""

from math import inf, isfinite
from time import perf_counter

from agent.algorithms.weighted_astar import WeightedAStar
from agent.memory import RunGraph


def grid_search(graph, start, target, heuristic='l1', low=1, high=10, step=1, score=None):
    """Try each w from low to high and keep the best cost/duration compromise.

    Bounds must be finite and at least 1. The default sweep is 1, 2, …, 10.
    Each trial records the path cost and the search duration. The best w
    minimizes cost/best_cost + duration/best_duration. `score` replaces that
    formula when another compromise is needed.
    """
    score = _score if score is None else score
    trials = []
    for w in _weights(low, high, step):
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
        trial['score'] = score(trial, best_cost, best_duration)
    best = min(trials, key=lambda trial: (trial['score'], trial['w']))
    return dict(best=best, trials=trials)


def graph_from_weights(weights):
    """Build the same movement graph as a run: each step costs the destination cell."""
    if not weights or any(len(row) != len(weights[0]) for row in weights):
        raise ValueError('The map must be a non-empty rectangle')
    cells = [
        {'position': {'x': x, 'y': y}, 'weight': weight}
        for y, row in enumerate(weights)
        for x, weight in enumerate(row)
        if weight is not None
    ]
    if not cells:
        raise ValueError('The map has no walkable cell')
    memory = RunGraph()
    memory.seed({'walkable_cells': cells})
    return memory.view()


def _weights(low, high, step):
    low, high, step = float(low), float(high), float(step)
    if not isfinite(low) or not isfinite(high) or not isfinite(step):
        raise ValueError('bounds and step must be finite')
    if low < 1 or high < 1:
        raise ValueError('bounds must belong to [1, +inf]')
    if low > high:
        raise ValueError('low must be lower than or equal to high')
    if step <= 0:
        raise ValueError('step must be positive')
    count = int((high - low) / step + 1e-9) + 1
    values = [low + index * step for index in range(count)]
    return [value for value in values if value <= high + step * 1e-9]


def _path_cost(graph, path):
    if not path:
        return inf
    return sum(graph.edges[left][right] for left, right in zip(path, path[1:]))


def _score(trial, best_cost, best_duration):
    if trial['cost'] is inf:
        return inf
    cost_ratio = 1.0 if best_cost == 0 else trial['cost'] / best_cost
    if best_duration == 0:
        duration_ratio = 0.0 if trial['duration'] == 0 else inf
    else:
        duration_ratio = trial['duration'] / best_duration
    return cost_ratio + duration_ratio


def weighted_score(trial, best_cost, best_duration):
    """Ten times the relative cost, plus the relative duration.

    The ratios are the same ones as ``_score``. A cheaper path stays ahead
    unless its search is much slower.
    """
    if trial['cost'] is inf:
        return inf
    cost_ratio = 1.0 if best_cost == 0 else trial['cost'] / best_cost
    if best_duration == 0:
        duration_ratio = 0.0 if trial['duration'] == 0 else inf
    else:
        duration_ratio = trial['duration'] / best_duration
    return 10 * cost_ratio + duration_ratio
