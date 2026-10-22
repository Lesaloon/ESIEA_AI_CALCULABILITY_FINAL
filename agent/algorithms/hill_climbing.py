"""Hill climbing over the weighted A* parameter w."""

from math import isfinite
from time import perf_counter

from agent.algorithms.grid_search import _path_cost, _score
from agent.algorithms.weighted_astar import WeightedAStar


def hill_climbing(graph, start, target, heuristic='l1', w=1, step=1, limit=100, score=None):
    """Walk from w by `step` until the current value is a local minimum.

    Neighbors are w - step and w + step. The neighbor below 1 is ignored.
    Each candidate uses the same cost/duration score as the grid search.
    The walk moves to the best neighbor when that score is strictly better,
    and stops when neither neighbor improves it. `limit` is the maximum
    number of moves. `score` replaces the default formula when set.
    """
    w, step, limit = _parameters(w, step, limit)
    score = _score if score is None else score
    trials_by_index = {}

    def evaluate(index):
        if index not in trials_by_index:
            weight = w + index * step
            algorithm = WeightedAStar(heuristic, weight)
            started = perf_counter()
            result = algorithm.search(graph, start, target)
            duration = perf_counter() - started
            trials_by_index[index] = dict(
                w=weight,
                cost=_path_cost(graph, result.path),
                duration=duration,
                expansions=len(result.trace.expanded),
                path=result.path,
            )
        return trials_by_index[index]

    current = 0
    for _ in range(limit):
        neighbors = [current + 1]
        if w + (current - 1) * step >= 1 - 1e-9:
            neighbors.append(current - 1)
        window = [current, *neighbors]
        for index in window:
            evaluate(index)
        group = [trials_by_index[index] for index in window]
        best_cost = min(trial['cost'] for trial in group)
        best_duration = min(trial['duration'] for trial in group)

        def ranked(index):
            return score(trials_by_index[index], best_cost, best_duration)

        chosen = min(neighbors, key=lambda index: (ranked(index), trials_by_index[index]['w']))
        if ranked(chosen) < ranked(current):
            current = chosen
        else:
            break

    trials = list(trials_by_index.values())
    best_cost = min(trial['cost'] for trial in trials)
    best_duration = min(trial['duration'] for trial in trials)
    for trial in trials:
        trial['score'] = score(trial, best_cost, best_duration)
    return dict(best=trials_by_index[current], trials=trials)


def _parameters(w, step, limit):
    w, step = float(w), float(step)
    if not isfinite(w) or not isfinite(step):
        raise ValueError('w and step must be finite')
    if w < 1:
        raise ValueError('w must belong to [1, +inf]')
    if step <= 0:
        raise ValueError('step must be positive')
    if type(limit) is not int or limit < 1:
        raise ValueError('limit must be a positive integer')
    return w, step, limit
