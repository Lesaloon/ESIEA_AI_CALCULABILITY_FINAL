"""Weighted shortest-path planners for the discovered graph."""

from heapq import heappop, heappush
from math import inf

from agent.distances import distance
from agent.models import DiscoveredGraphView, PlanningResult, Position, SearchTrace


def _path_to(parent: dict[Position, Position | None], target: Position) -> list[Position]:
    path = []
    node = target
    while node is not None:
        path.append(node)
        node = parent[node]
    return list(reversed(path))


class DijkstraPlanner:
    """Find minimum-cost paths with Dijkstra's shortest-path algorithm."""

    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        costs = {start: 0.0}
        parent: dict[Position, Position | None] = {start: None}
        frontier = [(0.0, start)]
        settled = set()
        expanded = []

        while frontier:
            cost, node = heappop(frontier)
            if cost != costs[node] or node in settled:
                continue
            settled.add(node)
            expanded.append(node)

            if node == target:
                path = _path_to(parent, target)
                remaining = sorted(
                    (candidate for candidate in costs if candidate not in settled),
                    key=lambda candidate: (costs[candidate], candidate),
                )
                scores = [
                    {'x': x, 'y': y, 'g': costs[(x, y)], 'h': 0, 'f': costs[(x, y)]}
                    for x, y in sorted(costs)
                ]
                return PlanningResult(path, SearchTrace(expanded, remaining, path, scores))

            for neighbor, movement_cost in sorted(graph.edges.get(node, {}).items()):
                candidate_cost = cost + movement_cost
                if candidate_cost < costs.get(neighbor, inf):
                    costs[neighbor] = candidate_cost
                    parent[neighbor] = node
                    heappush(frontier, (candidate_cost, neighbor))

        scores = [
            {'x': x, 'y': y, 'g': costs[(x, y)], 'h': 0, 'f': costs[(x, y)]}
            for x, y in sorted(costs)
        ]
        return PlanningResult([], SearchTrace(expanded, scores=scores))


class AStarPlanner:
    """Find weighted paths with A* and a configurable distance heuristic."""

    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        start_h = distance(start, target, self.heuristic)
        costs = {start: 0.0}
        heuristics = {start: start_h}
        parent: dict[Position, Position | None] = {start: None}
        frontier = [(start_h, start, 0.0)]
        expanded_at: dict[Position, float] = {}
        expanded = []

        while frontier:
            _, node, cost = heappop(frontier)
            if cost != costs[node] or expanded_at.get(node, inf) <= cost:
                continue
            expanded_at[node] = cost
            expanded.append(node)

            if node == target:
                path = _path_to(parent, target)
                remaining = sorted(
                    (candidate for candidate in costs
                     if costs[candidate] < expanded_at.get(candidate, inf)),
                    key=lambda candidate: (costs[candidate] + heuristics[candidate], candidate),
                )
                scores = [
                    {'x': x, 'y': y, 'g': costs[(x, y)], 'h': heuristics[(x, y)],
                     'f': costs[(x, y)] + heuristics[(x, y)]}
                    for x, y in sorted(costs)
                ]
                return PlanningResult(path, SearchTrace(expanded, remaining, path, scores))

            for neighbor, movement_cost in sorted(graph.edges.get(node, {}).items()):
                candidate_cost = cost + movement_cost
                if candidate_cost < costs.get(neighbor, inf):
                    heuristic = distance(neighbor, target, self.heuristic)
                    costs[neighbor] = candidate_cost
                    heuristics[neighbor] = heuristic
                    parent[neighbor] = node
                    heappush(frontier, (candidate_cost + heuristic, neighbor, candidate_cost))

        scores = [
            {'x': x, 'y': y, 'g': costs[(x, y)], 'h': heuristics[(x, y)],
             'f': costs[(x, y)] + heuristics[(x, y)]}
            for x, y in sorted(costs)
        ]
        return PlanningResult([], SearchTrace(expanded, scores=scores))
