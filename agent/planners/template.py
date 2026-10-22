"""Dijkstra and A* planners on the discovered graph."""

import heapq

from agent.distances import distance
from agent.models import DiscoveredGraphView, PlanningResult, Position, SearchTrace


def _rebuild(parent: dict, target: Position) -> list[Position]:
    path = []
    node = target
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()
    return path


def _search(graph: DiscoveredGraphView, start: Position, target: Position, h) -> PlanningResult:
    """Shared best-first loop: h = 0 gives Dijkstra, h = distance gives A*.

    The queue holds (f, g, node); ties on f and g fall back to the position,
    which keeps the result deterministic. The graph is never mutated.
    """
    if start == target:
        return PlanningResult([start], SearchTrace([start], [], [start]))

    cost = {start: 0}
    parent = {start: None}
    queue = [(h(start), 0, start)]
    expanded = []
    scores = []

    while queue:
        _, g, node = heapq.heappop(queue)
        if g > cost[node]:  # stale entry: a cheaper route was found later
            continue
        expanded.append(node)
        scores.append({'x': node[0], 'y': node[1], 'g': g, 'h': h(node), 'f': g + h(node)})
        if node == target:
            path = _rebuild(parent, target)
            frontier = sorted({n for _, c, n in queue if c == cost[n]})
            return PlanningResult(path, SearchTrace(expanded, frontier, path, scores))
        for neighbor, weight in graph.edges.get(node, {}).items():
            new_g = g + weight
            if neighbor not in cost or new_g < cost[neighbor]:
                cost[neighbor] = new_g
                parent[neighbor] = node
                heapq.heappush(queue, (new_g + h(neighbor), new_g, neighbor))

    return PlanningResult([], SearchTrace(expanded, [], [], scores))


class DijkstraPlanner:
    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        return _search(graph, start, target, lambda node: 0)


class AStarPlanner:
    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        return _search(graph, start, target,
                       lambda node: distance(node, target, self.heuristic))
