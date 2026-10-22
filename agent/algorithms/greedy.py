"""Greedy best-first search: always expands the node that looks closest to the
target. Fast, but ignores the cost already paid, so routes are not minimum-cost."""

from heapq import heappop, heappush

from agent.distances import distance
from agent.models import PlanningResult, SearchTrace


class Greedy:
    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def search(self, graph, start, target):
        # A node's parent is fixed when first discovered, so each node enters
        # the heap once and every heap entry is an unexpanded node.
        parent = {start: None}
        frontier = [(distance(start, target, self.heuristic), start)]
        heap_peak = 1
        expanded = []
        scores = []
        path = []
        while frontier:
            h, node = heappop(frontier)
            expanded.append(node)
            scores.append(dict(x=node[0], y=node[1], h=h))
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
            heap_peak = max(heap_peak, len(frontier))
        remaining = [node for _, node in sorted(frontier)]
        return PlanningResult(path, SearchTrace(expanded, remaining, path, scores, heap_peak))
