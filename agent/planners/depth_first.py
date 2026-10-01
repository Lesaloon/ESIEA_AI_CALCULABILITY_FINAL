"""Depth-first search: finds a route, usually not the shortest; ignores weights."""

from agent.models import PlanningResult, SearchTrace


class DepthFirstPlanner:
    def plan(self, graph, start, target):
        # Each stack entry remembers the node that pushed it, so the parent of a
        # node is the one it was actually reached from when popped.
        stack = [(start, None)]
        parent = {}
        expanded = []
        while stack:
            node, previous = stack.pop()
            if node in parent:
                continue
            parent[node] = previous
            expanded.append(node)
            if node == target:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                frontier = list(dict.fromkeys(n for n, _ in stack if n not in parent))
                return PlanningResult(path, SearchTrace(expanded, frontier, path))
            # Reverse-sorted push so neighbors are explored in sorted order.
            for neighbor in sorted(graph.edges.get(node, {}), reverse=True):
                if neighbor not in parent:
                    stack.append((neighbor, node))
        return PlanningResult([], SearchTrace(expanded))
