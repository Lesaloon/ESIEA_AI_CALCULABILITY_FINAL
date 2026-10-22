"""Find a weighted A* w with the same search as main algo 1 and a weighted score."""

from agent.algorithms.grid_search import graph_from_weights, grid_search, weighted_score
from agent.algorithms.hill_climbing import hill_climbing
from agent.algorithms.main_algo_1 import weight_ceiling


def main_algo_2(weights, start, target, heuristic='l1'):
    """Search [1, ceiling] with 100 weights, then hill-climb the 10 best.

    The steps and parameters match ``main_algo_1``: the ceiling comes from
    ``weight_ceiling``, the grid has 100 values, and each of the ten best
    scores is hill-climbed with a step of 0.1. Scores use ``weighted_score``,
    ten times the relative cost plus the relative duration.
    """
    ceiling = weight_ceiling(weights)
    graph = graph_from_weights(weights)
    step = (ceiling - 1) / 99 if ceiling > 1 else 1.0
    grid = grid_search(graph, start, target, heuristic, 1, ceiling, step, score=weighted_score)
    seeds = sorted(grid['trials'], key=lambda trial: (trial['score'], trial['w']))[:10]
    climbs = [
        hill_climbing(graph, start, target, heuristic, seed['w'], 0.1, score=weighted_score)
        for seed in seeds
    ]
    finals = [dict(climb['best']) for climb in climbs]
    best_cost = min(trial['cost'] for trial in finals)
    best_duration = min(trial['duration'] for trial in finals)
    for trial in finals:
        trial['score'] = weighted_score(trial, best_cost, best_duration)
    best = min(finals, key=lambda trial: (trial['score'], trial['w']))
    return dict(ceiling=ceiling, grid=grid, climbs=climbs, best=best)
