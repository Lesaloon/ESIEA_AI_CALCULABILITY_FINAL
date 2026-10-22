"""Depth-first search: finds a route, usually not the shortest; ignores weights."""

from agent.models import PlanningResult, SearchTrace


class DepthFirst:
    def __init__(self, heuristic=None):
        pass  # Uninformed: the heuristic is not used.

    def search(self, graph, start, target):
        # Each entry remembers the node that pushed it, so a node's parent is
        # the one it was actually reached from when popped.
        stack = [(start, None)]
        parent = {}
        heap_peak = 1
        expanded = []
        path = []
        while stack:
            node, previous = stack.pop()
            if node in parent:
                continue
            parent[node] = previous
            expanded.append(node)
            if node == target:
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                break
            # Reverse-sorted push so neighbors are explored in sorted order.
            for neighbor in sorted(graph.edges.get(node, {}), reverse=True):
                if neighbor not in parent:
                    stack.append((neighbor, node))
            heap_peak = max(heap_peak, len(stack))
        frontier = list(dict.fromkeys(n for n, _ in stack if n not in parent))
        return PlanningResult(path, SearchTrace(expanded, frontier, path, heap_peak=heap_peak))
