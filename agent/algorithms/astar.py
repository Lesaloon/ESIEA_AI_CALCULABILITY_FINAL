"""Weighted A* search on the complete frozen run graph.

Priority is f = g + weight * h. weight = 1 is classic A*; weight > 1 trusts the
heuristic more: fewer expansions, but the route may cost up to `weight` times the
optimum (when h is admissible).
"""

from heapq import heappop, heappush
from math import inf

from agent.distances import distance
from agent.models import PlanningResult, SearchTrace


class AStar:
    def __init__(self, heuristic='l1', weight=1.0):
        self.heuristic = heuristic
        self.weight = weight

    def estimate(self, node, target):
        return self.weight * distance(node, target, self.heuristic)

    def search(self, graph, start, target, trace=True):
        costs = {start: 0.0}
        heuristics = {start: self.estimate(start, target)}
        parent = {start: None}
        frontier = [(heuristics[start], start, 0.0)]
        expanded_at = {}
        expanded = []
        path = []

        while frontier:
            _, node, cost = heappop(frontier)
            if cost != costs[node] or expanded_at.get(node, inf) <= cost:
                continue
            expanded_at[node] = cost
            expanded.append(node)
            if node == target:
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                break
            for neighbor, movement_cost in sorted(graph.edges.get(node, {}).items()):
                candidate_cost = cost + movement_cost
                if candidate_cost < costs.get(neighbor, inf):
                    costs[neighbor] = candidate_cost
                    heuristics[neighbor] = self.estimate(neighbor, target)
                    parent[neighbor] = node
                    heappush(frontier, (candidate_cost + heuristics[neighbor], neighbor, candidate_cost))

        if not trace:
            return PlanningResult(path, SearchTrace(expanded, [], path, []))
        remaining = sorted(
            (node for node in costs if costs[node] < expanded_at.get(node, inf)),
            key=lambda node: (costs[node] + heuristics[node], node),
        )
        scores = [dict(x=x, y=y, g=costs[(x, y)], h=heuristics[(x, y)],
                       f=costs[(x, y)] + heuristics[(x, y)]) for x, y in sorted(costs)]
        return PlanningResult(path, SearchTrace(expanded, remaining, path, scores))
