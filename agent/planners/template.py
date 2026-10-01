"""Weighted planners: Dijkstra, and A* which adds a heuristic to the same search."""

import heapq

from agent.distances import distance
from agent.models import DiscoveredGraphView, PlanningResult, Position, SearchTrace


class DijkstraPlanner:
    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        return _best_first(graph, start, target, 'zero')


class AStarPlanner:
    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        return _best_first(graph, start, target, self.heuristic)


def _best_first(graph: DiscoveredGraphView, start: Position, target: Position,
                heuristic: str) -> PlanningResult:
    """Expand nodes by lowest g + h, where g is the directed cost from start.

    With the 'zero' heuristic this is Dijkstra. A node is expanded again if a
    cheaper route to it appears later, so inconsistent heuristics (squared L2,
    MSE) still terminate; they may return a costlier path, as documented.
    """
    def h(node):
        return distance(node, target, heuristic)

    best = {start: 0.0}
    parent = {start: None}
    # Ties on f prefer the node closer to the target, then the smaller coordinate.
    heap = [(h(start), h(start), start)]
    expanded = []
    scores = []
    while heap:
        f, h_node, node = heapq.heappop(heap)
        g = best[node]
        if f > g + h_node:
            continue  # Stale entry: a cheaper route to this node was found since.
        expanded.append(node)
        scores.append({'x': node[0], 'y': node[1], 'g': g, 'h': h_node, 'f': f})
        if node == target:
            path = []
            while node is not None:
                path.append(node)
                node = parent[node]
            path.reverse()
            done = set(expanded)
            frontier = list(dict.fromkeys(n for _, _, n in sorted(heap) if n not in done))
            return PlanningResult(path, SearchTrace(expanded, frontier, path, scores))
        for neighbor, cost in sorted(graph.edges.get(node, {}).items()):
            new_g = g + cost
            if new_g < best.get(neighbor, float('inf')):
                best[neighbor] = new_g
                parent[neighbor] = node
                h_neighbor = h(neighbor)
                heapq.heappush(heap, (new_g + h_neighbor, h_neighbor, neighbor))
    return PlanningResult([], SearchTrace(expanded, scores=scores))
