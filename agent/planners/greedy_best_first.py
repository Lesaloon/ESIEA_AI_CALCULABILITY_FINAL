"""Greedy best-first search: always expands the node that looks closest to the
target. Fast, but ignores the cost already paid, so routes are not minimum-cost."""

import heapq

from agent.distances import distance
from agent.models import PlanningResult, SearchTrace


class GreedyBestFirstPlanner:
    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def plan(self, graph, start, target):
        def h(node):
            return distance(node, target, self.heuristic)

        # A node's parent is fixed when first discovered, so each node enters the
        # heap once and every heap entry is an unexpanded node.
        parent = {start: None}
        heap = [(h(start), start)]
        expanded = []
        scores = []
        while heap:
            h_node, node = heapq.heappop(heap)
            expanded.append(node)
            scores.append({'x': node[0], 'y': node[1], 'h': h_node})
            if node == target:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                frontier = [n for _, n in sorted(heap)]
                return PlanningResult(path, SearchTrace(expanded, frontier, path, scores))
            for neighbor in sorted(graph.edges.get(node, {})):
                if neighbor not in parent:
                    parent[neighbor] = node
                    heapq.heappush(heap, (h(neighbor), neighbor))
        return PlanningResult([], SearchTrace(expanded, scores=scores))
