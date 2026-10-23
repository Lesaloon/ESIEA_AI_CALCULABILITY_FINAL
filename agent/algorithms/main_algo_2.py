"""Find a weighted A* w with the same search as main algo 1 and a fixed reference score."""

from agent.algorithms.grid_search import graph_from_weights, grid_search, importance, reference_score, run_trial
from agent.algorithms.hill_climbing import hill_climbing
from agent.algorithms.main_algo_1 import weight_ceiling


def main_algo_2(weights, start, target, heuristic='l1', a=1.0, b=1.0, c=0.0):
    """Search [1, ceiling] with 100 weights, then hill-climb the 10 best.

    The steps and parameters match ``main_algo_1``: the ceiling comes from
    ``weight_ceiling``, the grid has 100 values, and each of the ten best
    scores is hill-climbed with a step of 0.1. Every trial is scored against
    one A* run at w = 1 with the same heuristic:

    a * cost / cost_ref + b * duration / duration_ref + c * memory / memory_ref.

    ``a`` and ``b`` default to 1. ``c`` defaults to 0, so memory is measured
    but left out of the score. The reference is not the minimum of the batch.
    """
    a, b, c = importance(a, b, c)
    ceiling = weight_ceiling(weights)
    graph = graph_from_weights(weights)
    reference = run_trial(graph, start, target, heuristic, 1.0, memory=True)

    def score(trial, _best_cost, _best_duration):
        return reference_score(trial, reference, a, b, c)

    step = (ceiling - 1) / 99 if ceiling > 1 else 1.0
    grid = grid_search(graph, start, target, heuristic, 1, ceiling, step, score=score, memory=True)
    seeds = sorted(grid['trials'], key=lambda trial: (trial['score'], trial['w']))[:10]
    climbs = [
        hill_climbing(graph, start, target, heuristic, seed['w'], 0.1, score=score, memory=True)
        for seed in seeds
    ]
    finals = [dict(climb['best']) for climb in climbs]
    best = min(finals, key=lambda trial: (trial['score'], trial['w']))
    return dict(ceiling=ceiling, reference=reference, importance=dict(a=a, b=b, c=c),
                grid=grid, climbs=climbs, best=best)
