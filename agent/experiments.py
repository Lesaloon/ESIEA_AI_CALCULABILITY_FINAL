"""Experiments launched from the control panel (POST /experiments/...).

The agent searches on a complete, known map, so an experiment builds its own
maps in memory and calls the search algorithms directly: no run, no gRPC, no
turn delay. Maps follow the environment's rules: entering a cell costs its
weight (1-9), diagonals included when the connectivity is 8.

1. benchmark(): compare Dijkstra, A*, weighted A* and greedy across
   connectivity (4/8), heuristic, grid size and obstacle (none, U, wall, random).
2. transfer(): take a tuned (heuristic, weight) found on one configuration and
   test it on other configurations, against classic A*, a re-optimization per
   configuration (grid search) and a single "robust" pair optimized on average.
"""

import random
import tracemalloc
from dataclasses import dataclass
from itertools import product
from math import inf
from statistics import mean, median
from time import perf_counter

from agent.algorithms.astar import AStar
from agent.algorithms.dijkstra import Dijkstra
from agent.algorithms.greedy import Greedy
from agent.algorithms.optimizers import REFERENCE, Evaluator, GridSearch, path_cost
from agent.models import GraphView

STRAIGHT = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))
OBSTACLES = ('none', 'u', 'wall', 'random')
OBSTACLE_LABELS = {'none': 'No obstacle', 'u': 'U trap', 'wall': 'Vertical wall', 'random': 'Random walls'}
ALGORITHMS = {
    'dijkstra': ('Dijkstra', lambda h, w: Dijkstra()),
    'astar': ('A*', lambda h, w: AStar(h, 1.0)),
    'weighted_astar': ('Weighted A*', lambda h, w: AStar(h, w)),
    'greedy': ('Greedy', lambda h, w: Greedy(h)),
}
MAX_BENCHMARK_SEARCHES = 6000
MAX_TRANSFER_EVALUATIONS = 2500


@dataclass(frozen=True)
class MapConfig:
    size: int = 20
    connectivity: int = 8
    obstacle: str = 'u'
    weights: str = 'random'   # 'random' (1-9) or 'uniform' (all 1)
    seed: int = 0

    @property
    def label(self):
        return f'{self.size}×{self.size} · {self.connectivity}-conn · {OBSTACLE_LABELS[self.obstacle]}'


def endpoints(n):
    """Start on the left, goal on the right, both on the middle row."""
    return (1, n // 2), (n - 2, n // 2)


def obstacle_cells(kind, n, seed=0):
    """Obstacles between start and goal.

    u: a cup whose opening faces the start, so the straight line to the goal leads
    into its dead end (the trap of greedy search). wall: a vertical line with a
    two-cell passage at the bottom. random: about 20 % of cells, reproducible.
    """
    m = n // 2
    if kind == 'none':
        return set()
    if kind == 'u':
        r = max(2, n // 5)
        bottom = m + 1
        cells = {(bottom, y) for y in range(m - r, m + r + 1)}
        for y in (m - r, m + r):
            cells |= {(x, y) for x in range(bottom - r, bottom + 1)}
        return cells
    if kind == 'wall':
        return {(m, y) for y in range(n - 2)}
    if kind == 'random':
        rng = random.Random(seed)
        return {(x, y) for x in range(n) for y in range(n) if rng.random() < 0.2}
    raise ValueError(f'Unknown obstacle {kind!r}')


def graph_from_cells(cells, connectivity):
    """Directed graph over walkable `cells` ({position: weight}); entering a cell costs its weight."""
    moves = STRAIGHT + DIAGONAL if connectivity == 8 else STRAIGHT
    edges = {(x, y): {(x + dx, y + dy): cells[x + dx, y + dy] for dx, dy in moves if (x + dx, y + dy) in cells}
             for x, y in cells}
    return GraphView(edges, cells, frozenset())


def _reachable(graph, start, goal):
    seen, todo = {start}, [start]
    while todo:
        for neighbor in graph.edges[todo.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                todo.append(neighbor)
    return goal in seen


def build_map(config):
    """Return (graph, start, goal, preview). Random walls are redrawn until the goal is reachable."""
    n = config.size
    if not 8 <= n <= 40:
        raise ValueError('Map size must be between 8 and 40')
    if config.connectivity not in (4, 8):
        raise ValueError('Connectivity must be 4 or 8')
    start, goal = endpoints(n)
    seed = config.seed
    while True:
        walls = obstacle_cells(config.obstacle, n, seed) - {start, goal}
        rng = random.Random(config.seed)
        cells = {(x, y): (rng.randint(1, 9) if config.weights == 'random' else 1)
                 for x in range(n) for y in range(n) if (x, y) not in walls}
        # Reachable with 4 neighbors implies reachable with 8: one map works for both.
        if _reachable(graph_from_cells(cells, 4), start, goal):
            break
        if config.obstacle != 'random':
            raise ValueError('The goal is unreachable on this map')
        seed += 1000
    preview = [''.join('S' if (x, y) == start else 'G' if (x, y) == goal else '#' if (x, y) not in cells
                       else str(cells[x, y]) for x in range(n)) for y in range(n)]
    return graph_from_cells(cells, config.connectivity), start, goal, preview


def configs(sizes, connectivities, obstacles, weights='random', seed=0):
    return [MapConfig(s, c, o, weights, seed) for s, c, o in product(sizes, connectivities, obstacles)]


def run_search(algorithm, graph, start, goal, repeat):
    """Median time (ms) over `repeat` runs, peak memory (KB) of one traced run, and the result."""
    times = []
    for _ in range(repeat):
        began = perf_counter()
        result = algorithm.search(graph, start, goal, trace=False)
        times.append((perf_counter() - began) * 1000)
    tracing = tracemalloc.is_tracing()
    if not tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    baseline = tracemalloc.get_traced_memory()[0]
    algorithm.search(graph, start, goal, trace=False)
    memory_kb = (tracemalloc.get_traced_memory()[1] - baseline) / 1024
    if not tracing:
        tracemalloc.stop()
    return median(times), memory_kb, result


def benchmark(sizes=(20,), connectivities=(4, 8), heuristics=('l1', 'l2'), obstacles=('none', 'u', 'wall'),
              algorithms=('dijkstra', 'astar', 'weighted_astar', 'greedy'), weight=2.0, weights='random',
              seed=0, repeat=3):
    """One row per (map, algorithm, heuristic); Dijkstra ignores the heuristic and runs once per map.

    expanded = nodes taken out of the frontier (size of the explored graph);
    depth = moves of the route (depth of the goal in the search tree = steps the agent will walk);
    cost_ratio = route cost / Dijkstra's optimal cost.
    """
    plans = configs(sizes, connectivities, obstacles, weights, seed)
    jobs = [(a, h) for a in algorithms for h in (('zero',) if a == 'dijkstra' else heuristics)]
    if len(plans) * len(jobs) * (repeat + 1) > MAX_BENCHMARK_SEARCHES:
        raise ValueError('Too many combinations: select fewer sizes, obstacles or algorithms')
    rows, maps = [], []
    for config in plans:
        graph, start, goal, preview = build_map(config)
        optimal = path_cost(graph, Dijkstra().search(graph, start, goal, trace=False).path)
        maps.append(dict(config=config.__dict__, label=config.label, preview=preview, optimal_cost=optimal))
        reference = None
        for algorithm_id, heuristic in jobs:
            label, factory = ALGORITHMS[algorithm_id]
            time_ms, memory_kb, result = run_search(factory(heuristic, weight), graph, start, goal, repeat)
            cost = path_cost(graph, result.path) if result.path else None
            row = dict(size=config.size, connectivity=config.connectivity, obstacle=config.obstacle,
                       algorithm=algorithm_id, label=label + (f' (w={weight:g})' if algorithm_id == 'weighted_astar' else ''),
                       heuristic='–' if algorithm_id == 'dijkstra' else heuristic,
                       admissible=algorithm_id == 'dijkstra' or admissible(heuristic, config.connectivity),
                       time_ms=time_ms, memory_kb=memory_kb, expanded=len(result.trace.expanded),
                       depth=len(result.path) - 1 if result.path else None, cost=cost,
                       cost_ratio=cost / optimal if cost is not None else None,
                       optimal=cost is not None and abs(cost - optimal) < 1e-9)
            if algorithm_id == 'dijkstra':
                reference = row
            rows.append(row)
        for row in rows[-len(jobs):]:
            row['expanded_vs_dijkstra'] = row['expanded'] / reference['expanded'] if reference else None
    return dict(rows=rows, maps=maps, weight=weight, repeat=repeat)


def admissible(heuristic, connectivity):
    """With a minimum entry cost of 1: every listed metric is a lower bound with 4 neighbors,
    but a diagonal covers dx = dy = 1 for a cost of 1, so only L∞ (and zero) stay admissible with 8."""
    if heuristic in ('zero', 'linf'):
        return True
    return connectivity == 4 and heuristic in ('l1', 'l2')


def transfer(heuristic='linf', weight=2.0, sizes=(10, 20, 30), connectivities=(4, 8),
             obstacles=('none', 'u', 'wall', 'random'), weights='random', seed=0, lock_heuristic=False,
             weight_min=1.0, weight_max=5.0, weight_step=0.5, cost_weight=1.0, time_weight=1.0, memory_weight=1.0):
    """Test a tuned (heuristic, weight) on several configurations.

    Each configuration gets its own Evaluator: score = importance-weighted ratios of cost,
    time and memory against classic A* (L∞, w = 1) on that same map, so 3 means
    "as good as classic A*" with the default importances, and lower is better.
    Four strategies are compared on every map:
      fixed     the solution found on the default configuration, reused as is;
      reference classic A* (L∞, w = 1);
      robust    the single pair with the best mean score over all these maps;
      retuned   a grid search redone on each map (the best possible on the grid, but costly).
    """
    importance = dict(cost_weight=cost_weight, time_weight=time_weight, memory_weight=memory_weight)
    grid = GridSearch(dict(lock_heuristic=int(lock_heuristic), weight_min=weight_min, weight_max=weight_max,
                           weight_step=weight_step, **importance))
    plans = configs(sizes, connectivities, obstacles, weights, seed)
    candidates = list(product(grid.heuristics(heuristic),
                              [round(weight_min + i * weight_step, 3)
                               for i in range(int((weight_max - weight_min) / weight_step + 1e-9) + 1)]))
    if len(plans) * (len(candidates) + 2) > MAX_TRANSFER_EVALUATIONS:
        raise ValueError('Too many evaluations: select fewer sizes/obstacles or a coarser grid')
    maps = []
    for config in plans:
        graph, start, goal, _ = build_map(config)
        evaluate = Evaluator(graph, start, goal, importance)
        optimal = path_cost(graph, Dijkstra().search(graph, start, goal, trace=False).path)
        evaluate(heuristic, weight)
        evaluate(*REFERENCE)
        best = grid.best_of(evaluate, candidates)
        trials = {(t['heuristic'], t['weight']): t for t in evaluate.trials}
        maps.append((config, optimal, trials, best))

    def mean_score(pair):
        scores = [trials[pair]['score'] for _, _, trials, _ in maps]
        return inf if None in scores else mean(scores)

    # Robust pair: best mean score over every map (a pair that fails on one map is excluded).
    robust = min(candidates, key=mean_score)
    rows = []
    for config, optimal, trials, best in maps:
        def strategy(pair, extra=False):
            t = trials[(pair[0], round(pair[1], 3))]
            data = dict(score=t['score'], cost=t['cost'], time_ms=t['time_ms'], memory_kb=t['memory_kb'],
                        expanded=t['expanded'], cost_ratio=t['cost'] / optimal if t['cost'] is not None else None)
            return dict(data, heuristic=pair[0], weight=pair[1]) if extra else data
        row = dict(config=config.__dict__, label=config.label, optimal_cost=optimal,
                   fixed=strategy((heuristic, weight)), reference=strategy(REFERENCE),
                   robust=strategy(robust), retuned=strategy(best, extra=True), evaluations=len(trials))
        fixed, retuned = row['fixed']['score'], row['retuned']['score']
        row['fixed']['regret'] = fixed - retuned if fixed is not None and retuned is not None else None
        rows.append(row)

    def average(key, field):
        values = [r[key][field] for r in rows if r[key][field] is not None]
        return mean(values) if values else None

    summary = {key: dict(mean_score=average(key, 'score'), mean_cost_ratio=average(key, 'cost_ratio'),
                         worst_cost_ratio=max((r[key]['cost_ratio'] for r in rows if r[key]['cost_ratio']), default=None),
                         mean_expanded=average(key, 'expanded'))
               for key in ('fixed', 'reference', 'robust', 'retuned')}
    summary['fixed']['mean_regret'] = average('fixed', 'regret')
    summary['robust'].update(heuristic=robust[0], weight=robust[1])
    summary['retuned']['evaluations'] = sum(r['evaluations'] for r in rows)
    summary['retuned']['distinct'] = sorted({(r['retuned']['heuristic'], r['retuned']['weight']) for r in rows})
    return dict(solution=dict(heuristic=heuristic, weight=weight), rows=rows, summary=summary,
                grid=dict(weight_min=weight_min, weight_max=weight_max, weight_step=weight_step,
                          heuristics=list(grid.heuristics(heuristic))))
