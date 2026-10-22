"""Tune the weight w of weighted A* as an optimization problem.

Decision variable: w in [1, w_max] (w < 1 keeps optimality but explores more than
A*, so it is never worth it). Objective, averaged over a fixed set of maps so
that w is not tuned to a single map:

    F(w) = alpha * T/T_ref + beta * C/C* + gamma * H/H_ref

T is the search time, C the route cost and H the heap peak (memory). T_ref and
H_ref come from classic A* (w = 1, the baseline), C* is Dijkstra's optimal cost.
Constraint: C/C* <= max_cost_ratio when given, enforced as a penalty on F.

Search methods: grid search, random search, hill climbing, simulated annealing,
tabu search, and a hybrid (coarse grid, then tabu from its best point).
Evaluations are cached, so every method sees the same F.

Used by the agent API (POST /tuning) and from the repository root:
python -m agent.tuning --size 30 --max 10 50 100
"""

import argparse
import random
from collections import deque
from dataclasses import asdict, dataclass
from math import exp

from agent.algorithms.astar import AStar
from agent.algorithms.dijkstra import Dijkstra
from agent.benchmark import build_graph, endpoints, graph_from_cells, measure, path_cost, u_trap

LOW, STEP = 1.0, 0.2
PENALTY = 100.0


@dataclass(frozen=True)
class Settings:
    size: int = 30
    connectivity: int = 8
    heuristic: str = 'l1'
    alpha: float = 1.0
    beta: float = 1.0
    gamma: float = 1.0
    max_cost_ratio: float | None = None
    w_max: float = 50.0
    start: float = 2.4
    repeat: int = 3
    seed: int = 0


@dataclass(frozen=True)
class Evaluation:
    w: float
    f: float
    time_ratio: float
    cost_ratio: float
    heap_ratio: float


def random_weighted_map(n, seed, wall_ratio=0.2):
    """Random walls and weights 1-9; retries seeds until the goal is reachable."""
    start, goal = endpoints(n)
    while True:
        rng = random.Random(seed)
        walls = {(x, y) for x in range(n) for y in range(n) if rng.random() < wall_ratio} - {start, goal}
        weights = {(x, y): rng.randint(1, 9) for x in range(n) for y in range(n)}
        # Reachable with 4 neighbors implies reachable with 8.
        if _reachable(build_graph(n, walls, 4), start, goal):
            return walls, weights
        seed += 1000


def _reachable(graph, start, goal):
    seen, todo = {start}, [start]
    while todo:
        for neighbor in graph.edges[todo.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                todo.append(neighbor)
    return goal in seen


class Problem:
    """Evaluates F(w) on a fixed set of maps, with cached results."""

    def __init__(self, maps, settings):
        self.settings = settings
        self.cache = {}
        self.cases = []
        for graph, start, goal in maps:
            optimal = path_cost(graph, Dijkstra().search(graph, start, goal).path)
            seconds, result = measure(AStar(settings.heuristic), graph, start, goal, settings.repeat)
            self.cases.append((graph, start, goal, optimal, seconds, result.trace.heap_peak))

    def evaluate(self, w):
        w = round(w, 6)
        if w not in self.cache:
            s = self.settings
            time_ratio = cost_ratio = heap_ratio = 0.0
            for graph, start, goal, optimal, ref_seconds, ref_heap in self.cases:
                seconds, result = measure(AStar(s.heuristic, w), graph, start, goal, s.repeat)
                time_ratio += seconds / ref_seconds
                cost_ratio += path_cost(graph, result.path) / optimal
                heap_ratio += result.trace.heap_peak / ref_heap
            k = len(self.cases)
            time_ratio, cost_ratio, heap_ratio = time_ratio / k, cost_ratio / k, heap_ratio / k
            f = s.alpha * time_ratio + s.beta * cost_ratio + s.gamma * heap_ratio
            if s.max_cost_ratio is not None and cost_ratio > s.max_cost_ratio:
                f += PENALTY * (cost_ratio - s.max_cost_ratio)
            self.cache[w] = Evaluation(w, f, time_ratio, cost_ratio, heap_ratio)
        return self.cache[w]


class Run:
    """One method's view of the problem: keeps its evaluation order and best point."""

    def __init__(self, problem, high):
        self.problem = problem
        self.high = high
        self.order = []
        self.best = None

    def __call__(self, w):
        evaluation = self.problem.evaluate(min(max(w, LOW), self.high))
        if evaluation.w not in self.order:
            self.order.append(evaluation.w)
        if self.best is None or evaluation.f < self.best.f:
            self.best = evaluation
        return evaluation

    def neighbors(self, w, step):
        return [x for x in (w - step, w + step) if LOW <= x <= self.high]


def grid_search(run, values):
    for w in values:
        run(w)


def random_search(run, n, rng):
    for _ in range(n):
        run(rng.uniform(LOW, run.high))


def hill_climbing(run, w0, step):
    """Move to the best neighbor while it improves F; stops on a plateau or a local minimum."""
    current = run(w0)
    while True:
        best = min((run(w) for w in run.neighbors(current.w, step)), key=lambda e: e.f)
        if best.f >= current.f:
            return
        current = best


def simulated_annealing(run, w0, step, t0, cooling, iterations, rng):
    """Random neighbor; a worse one is kept with probability exp(-delta / T), T decreasing."""
    current, temperature = run(w0), t0
    for _ in range(iterations):
        candidate = run(rng.choice(run.neighbors(current.w, step)))
        delta = candidate.f - current.f
        if delta < 0 or rng.random() < exp(-delta / temperature):
            current = candidate
        temperature *= cooling


def tabu_search(run, w0, step, iterations, tabu_size):
    """Always move to the best non-tabu neighbor, even a worse one; recent w are tabu."""
    current = run(w0)
    tabu = deque([current.w], maxlen=tabu_size)
    for _ in range(iterations):
        options = [run(w) for w in run.neighbors(current.w, step) if round(w, 6) not in tabu]
        if not options:
            return
        current = min(options, key=lambda e: e.f)
        tabu.append(current.w)


def hybrid(run, step, points=10):
    """A coarse grid finds the right region, then tabu refines from its best point.

    The tabu phase gets enough moves to reach the neighboring grid points.
    """
    spacing = (run.high - LOW) / (points - 1)
    grid_search(run, [LOW + k * spacing for k in range(points)])
    tabu_search(run, run.best.w, step, max(20, round(spacing / step)), 10)


METHODS = (
    ('grid', 'Grid search (step 1)',
     lambda run, s, rng: grid_search(run, range(1, int(run.high) + 1))),
    ('random', 'Random search (20 draws)', lambda run, s, rng: random_search(run, 20, rng)),
    ('hill', 'Hill climbing', lambda run, s, rng: hill_climbing(run, s.start, STEP)),
    ('annealing', 'Simulated annealing',
     lambda run, s, rng: simulated_annealing(run, s.start, STEP, 1.0, 0.9, 60, rng)),
    ('tabu', 'Tabu search', lambda run, s, rng: tabu_search(run, s.start, STEP, 40, 10)),
    ('hybrid', 'Coarse grid + tabu', lambda run, s, rng: hybrid(run, STEP)),
)


def tuning_maps(settings):
    """The U trap plus three random weighted maps, all with the same endpoints."""
    n, c = settings.size, settings.connectivity
    start, goal = endpoints(n)
    maps = [(build_graph(n, u_trap(n), c), start, goal)]
    for k in range(3):
        walls, weights = random_weighted_map(n, settings.seed + k)
        maps.append((build_graph(n, walls, c, weights), start, goal))
    return maps


def run_tuning(settings):
    """Run every method on the same problem; returns plain data for the API and CLI."""
    if not LOW <= settings.start <= settings.w_max:
        raise ValueError('start must lie between 1 and w_max')
    problem = Problem(tuning_maps(settings), settings)
    rng = random.Random(settings.seed)
    methods = []
    for key, label, method in METHODS:
        run = Run(problem, settings.w_max)
        method(run, settings, rng)
        methods.append(dict(id=key, label=label, best=asdict(run.best),
                            evaluations=len(run.order), evaluated=run.order))
    curve = [asdict(problem.evaluate(w)) for w in range(1, int(settings.w_max) + 1)]
    return dict(settings=asdict(settings), baseline=asdict(problem.evaluate(1.0)),
                methods=methods, curve=curve)


def map_grid_search(cells, start, goal, settings):
    """Grid search of w on one map (the editor's grid, 8 neighbors), for picking w in the UI.

    `cells` maps each walkable position to its weight. Returns F for every integer w.
    """
    graph = graph_from_cells(cells, 8)
    if start not in cells or goal not in cells or not _reachable(graph, start, goal):
        raise ValueError('No route between start and goal on this map')
    problem = Problem([(graph, start, goal)], settings)
    curve = [asdict(problem.evaluate(w)) for w in range(1, int(settings.w_max) + 1)]
    return dict(baseline=asdict(problem.evaluate(1.0)), curve=curve,
                best=min(curve, key=lambda e: e['f']))


def main():
    parser = argparse.ArgumentParser(description='Tune the weight of weighted A* with several search methods.')
    parser.add_argument('--size', type=int, default=30, help='square map side (default 30)')
    parser.add_argument('--connectivity', type=int, choices=(4, 8), default=8)
    parser.add_argument('--heuristic', default='l1', choices=('l1', 'l2', 'linf'))
    parser.add_argument('--alpha', type=float, default=1.0, help='weight of search time in F')
    parser.add_argument('--beta', type=float, default=1.0, help='weight of route cost in F')
    parser.add_argument('--gamma', type=float, default=1.0, help='weight of heap size in F')
    parser.add_argument('--max-cost-ratio', type=float, help='constraint: cost at most this times optimal')
    parser.add_argument('--max', type=float, nargs='+', default=[50.0], help='upper bounds of w to compare')
    parser.add_argument('--start', type=float, default=2.4, help='starting w for local methods')
    parser.add_argument('--repeat', type=int, default=3, help='timing runs per evaluation')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--curve', action='store_true', help='also print F(w) for integer w')
    args = parser.parse_args()
    if args.size < 10:
        parser.error('--size must be at least 10 so the obstacles fit between start and goal')

    for w_max in args.max:
        settings = Settings(args.size, args.connectivity, args.heuristic, args.alpha, args.beta, args.gamma,
                            args.max_cost_ratio, w_max, args.start, args.repeat, args.seed)
        result = run_tuning(settings)
        constraint = f', cost <= {args.max_cost_ratio} x optimal' if args.max_cost_ratio else ''
        print(f'Maps {args.size}x{args.size} (U + 3 random weighted), connectivity {args.connectivity}, '
              f'heuristic {args.heuristic}, w in [1, {w_max:g}]')
        print(f'F = {args.alpha} x time/ref + {args.beta} x cost/optimal + {args.gamma} x heap/ref{constraint}')
        print(f"Baseline A* (w = 1): F = {result['baseline']['f']:.3f}\n")
        header = (f"{'method':<26}{'best w':>8}{'F':>8}{'time/ref':>10}{'cost/opt':>10}"
                  f"{'heap/ref':>10}{'evaluations':>13}")
        print(header)
        print('-' * len(header))
        for m in result['methods']:
            b = m['best']
            print(f"{m['label']:<26}{b['w']:>8.2f}{b['f']:>8.3f}{b['time_ratio']:>10.2f}"
                  f"{b['cost_ratio']:>10.3f}{b['heap_ratio']:>10.2f}{m['evaluations']:>13}")
        if args.curve:
            print(f"\n{'w':>5}{'F':>8}{'cost/opt':>10}{'heap/ref':>10}")
            for e in result['curve']:
                print(f"{e['w']:>5g}{e['f']:>8.3f}{e['cost_ratio']:>10.3f}{e['heap_ratio']:>10.2f}")
        print()


if __name__ == '__main__':
    main()
