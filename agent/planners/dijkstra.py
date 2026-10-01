"""Dijkstra shortest paths. Same search as A*, with a zero heuristic."""

import heapq

from agent.distances import distance
from agent.models import DiscoveredGraphView, PlanningResult, Position, SearchTrace


def _reconstruct(parent: dict[Position, Position | None], node: Position) -> list[Position]:
    path = []
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()
    return path


def _heuristic(node: Position, target: Position, metric: str) -> float:
    if metric == 'zero':
        return 0.0
    return distance(node, target, metric)


def _trace(expanded: list[Position], heap: list, g_score: dict[Position, float],
           target: Position, metric: str, path: list[Position]) -> SearchTrace:
    expanded_nodes = set(expanded)
    frontier = []
    seen = set()
    for _priority, stored_g, node in sorted(heap):
        if node in seen or node in expanded_nodes or stored_g != g_score.get(node):
            continue
        seen.add(node)
        frontier.append(node)
    scores = []
    for node, g_cost in sorted(g_score.items()):
        h_cost = _heuristic(node, target, metric)
        scores.append({'x': node[0], 'y': node[1], 'g': g_cost, 'h': h_cost, 'f': g_cost + h_cost})
    return SearchTrace(list(expanded), frontier, path, scores)


def weighted_search(graph: DiscoveredGraphView, start: Position, target: Position,
                    metric: str) -> PlanningResult:
    """Expand the lowest g+h first. metric 'zero' is Dijkstra."""
    g_score = {start: 0.0}
    parent: dict[Position, Position | None] = {start: None}
    heap = [(_heuristic(start, target, metric), 0.0, start)]
    expanded: list[Position] = []

    while heap:
        _priority, g_cost, node = heapq.heappop(heap)
        if g_cost != g_score.get(node):
            continue
        expanded.append(node)
        if node == target:
            path = _reconstruct(parent, node)
            return PlanningResult(path, _trace(expanded, heap, g_score, target, metric, path))
        for neighbor, edge_cost in sorted(graph.edges.get(node, {}).items()):
            new_g = g_cost + edge_cost
            if new_g < g_score.get(neighbor, float('inf')):
                g_score[neighbor] = new_g
                parent[neighbor] = node
                heapq.heappush(heap, (new_g + _heuristic(neighbor, target, metric), new_g, neighbor))

    return PlanningResult([], _trace(expanded, heap, g_score, target, metric, []))


class DijkstraPlanner:
    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        return weighted_search(graph, start, target, 'zero')
