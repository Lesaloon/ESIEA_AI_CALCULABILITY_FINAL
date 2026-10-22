"""Compare the search algorithms on fully known maps, for the exercises.

Each algorithm searches once from start to goal on the whole map, so the numbers
reflect the algorithm itself rather than the agent's movement.

Configurations: 4- or 8-way connectivity, L1 or L2 heuristic, and an empty map,
a vertical wall, a U-shaped trap, or both. The vertical wall spans the whole
height, so those maps have no route: every algorithm must exhaust what it can
reach. Moves follow the environment's rules: entering a cell costs its weight,
diagonals included, and diagonals may pass between two obstacles.

From the repository root: python -m agent.benchmark --size 30
"""

import argparse
from statistics import median
from time import perf_counter

from agent.algorithms.astar import AStar
from agent.algorithms.breadth_first import BreadthFirst
from agent.algorithms.depth_first import DepthFirst
from agent.algorithms.dijkstra import Dijkstra
from agent.algorithms.greedy import Greedy
from agent.models import GraphView

STRAIGHT = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))
HEURISTICS = ('l1', 'l2')
WEIGHTS = (2, 5)


def endpoints(n):
    return (n // 6, n // 2), (5 * n // 6, n // 2)


def vertical_wall(n, x=None):
    """A full-height wall between start and goal: the goal is unreachable."""
    return {(n // 2 if x is None else x, y) for y in range(n)}


def u_trap(n):
    """A cup opening toward the start, with the goal behind its bottom."""
    top, bottom, left, right = n // 4, 3 * n // 4, n // 3, 2 * n // 3
    walls = {(right, y) for y in range(top, bottom + 1)}
    walls |= {(x, y) for x in range(left, right + 1) for y in (top, bottom)}
    return walls


def u_trap_and_wall(n):
    """The U, then the full-height wall between it and the goal."""
    return u_trap(n) | vertical_wall(n, 3 * n // 4)


MAPS = {'vide': lambda n: set(), 'ligne verticale': vertical_wall, 'U': u_trap,
        'U + ligne': u_trap_and_wall}


def build_graph(n, walls, connectivity, weights=None):
    """Full-map graph; `weights` maps cells to their cost (1 when omitted)."""
    weights = weights or {}
    cells = {(x, y): weights.get((x, y), 1) for x in range(n) for y in range(n) if (x, y) not in walls}
    return graph_from_cells(cells, connectivity)


def graph_from_cells(cells, connectivity=8):
    """Graph over walkable `cells` ({position: weight}); entering a cell costs its weight."""
    moves = STRAIGHT + DIAGONAL if connectivity == 8 else STRAIGHT
    edges = {(x, y): {(x + dx, y + dy): cells[x + dx, y + dy]
                      for dx, dy in moves if (x + dx, y + dy) in cells}
             for x, y in cells}
    return GraphView(edges, cells, frozenset())


def path_cost(graph, path):
    return sum(graph.edges[a][b] for a, b in zip(path, path[1:])) if path else None


def measure(algorithm, graph, start, goal, repeat):
    """Median wall-clock seconds over `repeat` runs, and the last result."""
    times = []
    for _ in range(repeat):
        t = perf_counter()
        result = algorithm.search(graph, start, goal)
        times.append(perf_counter() - t)
    return median(times), result


def algorithms():
    """(name, heuristic, algorithm) for every row; uninformed searches run once."""
    yield 'BFS', '-', BreadthFirst()
    yield 'DFS', '-', DepthFirst()
    yield 'Dijkstra', '-', Dijkstra()
    for h in HEURISTICS:
        yield 'Greedy', h, Greedy(h)
    for h in HEURISTICS:
        yield 'A*', h, AStar(h)
    for w in WEIGHTS:
        for h in HEURISTICS:
            yield f'A* w={w}', h, AStar(h, w)


def main():
    parser = argparse.ArgumentParser(description='Compare search algorithms across map configurations.')
    parser.add_argument('--size', type=int, default=30, help='square map side (default 30)')
    parser.add_argument('--repeat', type=int, default=5, help='timing runs per algorithm (default 5)')
    args = parser.parse_args()
    if args.size < 10:
        parser.error('--size must be at least 10 so the obstacles fit between start and goal')
    n = args.size
    start, goal = endpoints(n)

    header = (f"{'carte':<16}{'conn.':>6}  {'algo':<10}{'heur.':<6}{'temps ms':>10}"
              f"{'explorés':>10}{'tas max':>9}{'profondeur':>12}{'coût':>8}  optimal")
    print(f'Carte {n}x{n}, départ {start}, arrivée {goal}, tout déplacement coûte le poids de la case (1)\n')
    print(header)
    print('-' * len(header))
    for map_name, make_walls in MAPS.items():
        for connectivity in (4, 8):
            graph = build_graph(n, make_walls(n), connectivity)
            rows = []
            for name, h, algorithm in algorithms():
                seconds, result = measure(algorithm, graph, start, goal, args.repeat)
                rows.append((name, h, seconds, result, path_cost(graph, result.path)))
            # Dijkstra is the reference minimum cost for this configuration.
            best_cost = next(cost for name, *_, cost in rows if name == 'Dijkstra')
            for name, h, seconds, result, cost in rows:
                if cost is None:
                    depth, cost, optimal = '-', '-', 'pas de chemin'
                else:
                    depth = len(result.path) - 1
                    optimal = 'oui' if abs(cost - best_cost) < 1e-9 else 'non'
                    cost = f'{cost:.0f}'
                print(f'{map_name:<16}{connectivity:>6}  {name:<10}{h:<6}{seconds * 1000:>10.2f}'
                      f'{len(result.trace.expanded):>10}{result.trace.heap_peak:>9}{depth:>12}{cost:>8}'
                      f'  {optimal}')
            print()


if __name__ == '__main__':
    main()
