"""Weighted A* search on the complete frozen run graph."""

from heapq import heappop, heappush
from math import inf

from agent.distances import distance
from agent.models import PlanningResult, SearchTrace


class AStar:
    """Prioritize nodes by g + w*h, retaining a trace for the control panel."""

    def __init__(self, heuristic='l1', heuristic_weight=1.0):
        self.heuristic = heuristic
        self.heuristic_weight = heuristic_weight

    def estimate(self, node, target):
        """Return the weighted estimate w*h (also stored as h in the trace)."""
        return self.heuristic_weight * distance(node, target, self.heuristic)

    def search(self, graph, start, target):
        """Return a route including both endpoints, or an empty route if unreachable."""
        # g is the best known cost from the start; parent reconstructs that route.
        costs = {start: 0.0}
        heuristics = {start: self.estimate(start, target)}
        parent = {start: None}
        # Heap entries are (f, coordinates, g); coordinates break ties consistently.
        frontier = [(heuristics[start], start, 0.0)]
        # Track the cost of each expansion so a cheaper route can reopen a node.
        expanded_at = {}
        expanded = []
        path = []

        while frontier:
            _, node, cost = heappop(frontier)
            # Improved routes leave old entries in the heap. Skip stale entries
            # and nodes already expanded at an equal or lower cost.
            if cost != costs[node] or expanded_at.get(node, inf) <= cost:
                continue
            expanded_at[node] = cost
            expanded.append(node)
            if node == target:
                # Follow predecessors backwards, then put start before goal.
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                break
            # Sorted neighbors keep traversal deterministic for a fixed graph.
            for neighbor, movement_cost in sorted(graph.edges.get(node, {}).items()):
                candidate_cost = cost + movement_cost
                # Relax an edge only when it improves the neighbor's known g.
                if candidate_cost < costs.get(neighbor, inf):
                    costs[neighbor] = candidate_cost
                    heuristics[neighbor] = self.estimate(neighbor, target)
                    parent[neighbor] = node
                    heappush(frontier, (candidate_cost + heuristics[neighbor], neighbor, candidate_cost))

        # Build the logical frontier from best costs, excluding stale heap entries.
        remaining = sorted(
            (node for node in costs if costs[node] < expanded_at.get(node, inf)),
            key=lambda node: (costs[node] + heuristics[node], node),
        )
        scores = [dict(x=x, y=y, g=costs[(x, y)], h=heuristics[(x, y)],
                       f=costs[(x, y)] + heuristics[(x, y)]) for x, y in sorted(costs)]
        return PlanningResult(path, SearchTrace(expanded, remaining, path, scores))
