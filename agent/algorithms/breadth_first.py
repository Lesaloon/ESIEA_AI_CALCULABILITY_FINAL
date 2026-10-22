"""Breadth-first search: fewest moves, ignoring cell weights."""

from collections import deque

from agent.models import PlanningResult, SearchTrace


class BreadthFirst:
    def __init__(self, heuristic=None):
        pass  # Uninformed: the heuristic is not used.

    def search(self, graph, start, target):
        queue = deque([start])
        parent = {start: None}
        heap_peak = 1
        expanded = []
        path = []
        while queue:
            node = queue.popleft()
            expanded.append(node)
            if node == target:
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                break
            for neighbor in sorted(graph.edges.get(node, {})):
                if neighbor not in parent:
                    parent[neighbor] = node
                    queue.append(neighbor)
            heap_peak = max(heap_peak, len(queue))
        return PlanningResult(path, SearchTrace(expanded, list(queue), path, heap_peak=heap_peak))
