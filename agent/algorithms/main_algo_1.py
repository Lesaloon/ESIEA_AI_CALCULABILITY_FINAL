"""Find a weighted A* w by a grid search up to the map ceiling, then hill climbing."""

from math import isfinite

from agent.algorithms.grid_search import _score, graph_from_weights, grid_search
from agent.algorithms.hill_climbing import hill_climbing


def weight_ceiling(weights):
    """Largest cost gap on the grid, used as the upper bound of w.

    With the l1 heuristic, a larger w cannot change the search once it
    exceeds the most expensive possible path. That path pays the maximum
    cell weight at every step, and a path visits each walkable cell at most
    once. Obstacles are ``None``. The result is at least 1.
    """
    if not weights or any(len(row) != len(weights[0]) for row in weights):
        raise ValueError('The map must be a non-empty rectangle')
    walkable = [float(weight) for row in weights for weight in row if weight is not None]
    if not walkable:
        raise ValueError('The map has no walkable cell')
    if any(not isfinite(weight) or weight < 0 for weight in walkable):
        raise ValueError('cell weights must be finite and at least 0')
    return max(1.0, max(walkable) * (len(walkable) - 1))


def main_algo_1(weights, start, target, heuristic='l1'):
    """Search [1, ceiling] with 100 weights, then hill-climb the 10 best.

    The ceiling comes from ``weight_ceiling``. The grid uses 100 values
    from 1 to that ceiling. Each hill climb starts from one of the ten best
    scores and moves by 0.1, so it looks between the grid values. The kept
    result is the hill climb whose final w has the best cost/duration score
    among the ten.
    """
    ceiling = weight_ceiling(weights)
    graph = graph_from_weights(weights)
    step = (ceiling - 1) / 99 if ceiling > 1 else 1.0
    grid = grid_search(graph, start, target, heuristic, 1, ceiling, step)
    seeds = sorted(grid['trials'], key=lambda trial: (trial['score'], trial['w']))[:10]
    climbs = [
        hill_climbing(graph, start, target, heuristic, seed['w'], 0.1)
        for seed in seeds
    ]
    finals = [dict(climb['best']) for climb in climbs]
    best_cost = min(trial['cost'] for trial in finals)
    best_duration = min(trial['duration'] for trial in finals)
    for trial in finals:
        trial['score'] = _score(trial, best_cost, best_duration)
    best = min(finals, key=lambda trial: (trial['score'], trial['w']))
    return dict(ceiling=ceiling, grid=grid, climbs=climbs, best=best)
