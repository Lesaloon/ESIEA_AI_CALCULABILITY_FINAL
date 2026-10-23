"""Manual grid search over the weighted A* parameter w."""

import tracemalloc
from math import inf, isfinite
from statistics import median
from time import perf_counter

from agent.algorithms.weighted_astar import WeightedAStar
from agent.memory import RunGraph


def run_trial(graph, start, target, heuristic, w, memory=False, timing_repeats=1):
    """Run weighted A* and record its cost and duration.

    Duration is a single clock reading when `timing_repeats` is 1. A larger
    repeat count runs the search that many times and keeps the median duration,
    so one slow or fast run does not decide the score. When `memory` is set,
    the trial also records a peak traced memory in kilobytes. With one repeat
    that peak comes from the timed run. With several repeats it comes from a
    separate run, so tracing stays out of the median.
    """
    if type(timing_repeats) is not int or timing_repeats < 1:
        raise ValueError('timing repeats must be a positive integer')
    algorithm = WeightedAStar(heuristic, w)
    if timing_repeats == 1:
        tracing = False
        baseline = 0
        if memory:
            tracing = tracemalloc.is_tracing()
            if not tracing:
                tracemalloc.start()
            tracemalloc.reset_peak()
            baseline = tracemalloc.get_traced_memory()[0]
        started = perf_counter()
        result = algorithm.search(graph, start, target)
        duration = perf_counter() - started
        trial = _trial(w, result, graph, duration)
        if memory:
            trial['memory'] = max(tracemalloc.get_traced_memory()[1] - baseline, 0) / 1024
            if not tracing:
                tracemalloc.stop()
        return trial

    durations = []
    result = None
    for _ in range(timing_repeats):
        started = perf_counter()
        result = algorithm.search(graph, start, target)
        durations.append(perf_counter() - started)
    trial = _trial(w, result, graph, median(durations))
    if memory:
        trial['memory'] = _peak_memory(algorithm, graph, start, target)
    return trial


def _trial(w, result, graph, duration):
    return dict(
        w=w,
        cost=_path_cost(graph, result.path),
        duration=duration,
        expansions=len(result.trace.expanded),
        path=result.path,
    )


def _peak_memory(algorithm, graph, start, target):
    tracing = tracemalloc.is_tracing()
    if not tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    baseline = tracemalloc.get_traced_memory()[0]
    algorithm.search(graph, start, target)
    peak = max(tracemalloc.get_traced_memory()[1] - baseline, 0) / 1024
    if not tracing:
        tracemalloc.stop()
    return peak


def grid_search(graph, start, target, heuristic='l1', low=1, high=10, step=1, score=None, memory=False, timing_repeats=1):
    """Try each w from low to high and keep the best cost/duration compromise.

    Bounds must be finite and at least 1. The default sweep is 1, 2, …, 10.
    Each trial records the path cost and the search duration. The best w
    minimizes cost/best_cost + duration/best_duration. `score` replaces that
    formula when another compromise is needed. `memory` records the peak
    traced memory of each run. `timing_repeats` above 1 stores the median duration.
    """
    score = _score if score is None else score
    trials = []
    for w in _weights(low, high, step):
        trials.append(run_trial(graph, start, target, heuristic, w, memory, timing_repeats))

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


def reference_score(trial, reference, a=1.0, b=1.0, c=0.0):
    """Score one trial against a fixed A* reference.

    ``a``, ``b`` and ``c`` weight the cost, duration and memory ratios.
    A missing or zero reference stays finite when the trial matches it, and
    infinite when the trial is worse. ``c`` defaults to 0, so memory is
    ignored unless an importance is given. An unreachable trial stays infinite.
    """
    if trial['cost'] is inf or reference['cost'] is inf:
        return inf
    total = a * _ratio(trial['cost'], reference['cost']) + b * _ratio(trial['duration'], reference['duration'])
    if c:
        total += c * _ratio(trial.get('memory', 0.0), reference.get('memory', 0.0))
    return total


def importance(a, b, c):
    """Return finite importances a, b, c. At least one must be above zero."""
    values = []
    for name, value in (('a', a), ('b', b), ('c', c)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ValueError(f'{name} must be a finite number at least 0')
        values.append(float(value))
    if not any(values):
        raise ValueError('At least one of a, b and c must be above zero')
    return tuple(values)


def _ratio(value, reference):
    if reference == 0:
        return 0.0 if value == 0 else inf
    return value / reference
