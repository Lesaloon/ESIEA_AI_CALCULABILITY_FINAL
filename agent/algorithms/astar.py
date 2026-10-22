"""Weighted A* search on the complete frozen run graph."""

from heapq import heappop, heappush
from math import inf

from agent.distances import distance
from agent.models import PlanningResult, SearchTrace


class AStar:
    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def estimate(self, node, target):
        return distance(node, target, self.heuristic)

    def priority(self, cost, heuristic):
        return cost + heuristic

    def search(self, graph, start, target):
        costs = {start: 0.0}
        heuristics = {start: self.estimate(start, target)}
        parent = {start: None}
        frontier = [(self.priority(0.0, heuristics[start]), start, 0.0)]
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
                    heappush(frontier, (self.priority(candidate_cost, heuristics[neighbor]), neighbor, candidate_cost))

        remaining = sorted(
            (node for node in costs if costs[node] < expanded_at.get(node, inf)),
            key=lambda node: (self.priority(costs[node], heuristics[node]), node),
        )
        scores = [dict(x=x, y=y, g=costs[(x, y)], h=heuristics[(x, y)],
                       f=self.priority(costs[(x, y)], heuristics[(x, y)])) for x, y in sorted(costs)]
        return PlanningResult(path, SearchTrace(expanded, remaining, path, scores))
