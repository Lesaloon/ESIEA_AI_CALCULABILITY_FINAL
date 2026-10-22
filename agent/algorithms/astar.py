"""Weighted A* search on the complete frozen run graph.

Priority is f = g + weight * h: weight 0 gives Dijkstra, 1 classic A*, and a
large weight tends toward greedy best-first. With an admissible h and weight
w >= 1, the route costs at most w times the optimum.
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
        return distance(node, target, self.heuristic)

    def search(self, graph, start, target):
        weight = self.weight
        costs = {start: 0.0}
        heuristics = {start: self.estimate(start, target)}
        parent = {start: None}
        frontier = [(weight * heuristics[start], start, 0.0)]
        heap_peak = 1
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
                    heappush(frontier, (candidate_cost + weight * heuristics[neighbor], neighbor, candidate_cost))
            heap_peak = max(heap_peak, len(frontier))

        remaining = sorted(
            (node for node in costs if costs[node] < expanded_at.get(node, inf)),
            key=lambda node: (costs[node] + weight * heuristics[node], node),
        )
        scores = [dict(x=x, y=y, g=costs[(x, y)], h=heuristics[(x, y)],
                       f=costs[(x, y)] + weight * heuristics[(x, y)]) for x, y in sorted(costs)]
        return PlanningResult(path, SearchTrace(expanded, remaining, path, scores, heap_peak))
