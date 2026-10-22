"""Simulated annealing over the weighted A* parameter w."""

import random
from math import isfinite
from time import perf_counter

from agent.algorithms.grid_search import _path_cost, _score
from agent.algorithms.hill_climbing import _parameters
from agent.algorithms.weighted_astar import WeightedAStar


def simulated_annealing(graph, start, target, heuristic='l1', w=1, step=1, temperature=0.5, limit=100, seed=None):
    """Hill climbing that sometimes moves to a random neighbor.

    `temperature` belongs to [0, 1]. Before each move, a value e is drawn
    uniformly in [0, 1]. When e is greater than the temperature, the walk
    moves to a random neighbor. Otherwise it moves to the best neighbor,
    and stops when that neighbor is not strictly better, as in hill climbing.
    `limit` is the maximum number of moves.
    """
    w, step, limit = _parameters(w, step, limit)
    temperature = _temperature(temperature)
    picker = random.Random(seed)
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

        def score(index):
            return _score(trials_by_index[index], best_cost, best_duration)

        if picker.uniform(0, 1) > temperature:
            current = picker.choice(neighbors)
            continue
        chosen = min(neighbors, key=lambda index: (score(index), trials_by_index[index]['w']))
        if score(chosen) < score(current):
            current = chosen
        else:
            break

    trials = list(trials_by_index.values())
    best_cost = min(trial['cost'] for trial in trials)
    best_duration = min(trial['duration'] for trial in trials)
    for trial in trials:
        trial['score'] = _score(trial, best_cost, best_duration)
    return dict(best=trials_by_index[current], trials=trials)


def _temperature(temperature):
    temperature = float(temperature)
    if not isfinite(temperature) or not 0 <= temperature <= 1:
        raise ValueError('temperature must belong to [0, 1]')
    return temperature
