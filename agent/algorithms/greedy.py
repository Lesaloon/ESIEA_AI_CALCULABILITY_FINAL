"""Greedy best-first search: priority f = h only.

It always expands the node that looks closest to the target and ignores the
cost already paid (g). Fast on open maps, but routes are not minimum-cost and
the search is easily drawn into dead ends such as a U-shaped obstacle.
"""

from heapq import heappop, heappush

from agent.distances import distance
from agent.models import PlanningResult, SearchTrace


class Greedy:
    def __init__(self, heuristic='l1', weight=1.0):
        # `weight` is accepted for a uniform factory signature; f = h does not use it.
        self.heuristic = heuristic

    def search(self, graph, start, target, trace=True):
        # A node's parent is fixed when it is first discovered (closed-list greedy),
        # so each node enters the frontier at most once.
        parent = {start: None}
        frontier = [(distance(start, target, self.heuristic), start)]
        expanded, scores, path = [], [], []
        while frontier:
            h, node = heappop(frontier)
            expanded.append(node)
            if trace:
                scores.append(dict(x=node[0], y=node[1], h=h, f=h))
            if node == target:
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                break
            for neighbor in sorted(graph.edges.get(node, {})):
                if neighbor not in parent:
                    parent[neighbor] = node
                    heappush(frontier, (distance(neighbor, target, self.heuristic), neighbor))
        remaining = [node for _, node in sorted(frontier)] if trace else []
        return PlanningResult(path, SearchTrace(expanded, remaining, path, scores))
