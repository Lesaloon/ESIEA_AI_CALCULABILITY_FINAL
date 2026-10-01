"""Depth-first search. One branch is followed before backtracking; weights are ignored."""

from agent.models import PlanningResult, SearchTrace


class DepthFirstPlanner:
    def plan(self, graph, start, target):
        stack = [start]
        parent = {start: None}
        expanded = []
        while stack:
            node = stack.pop()
            expanded.append(node)
            if node == target:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return PlanningResult(path, SearchTrace(expanded, list(reversed(stack)), path))
            # Push larger coordinates first so the smaller one is explored next.
            for neighbor in sorted(graph.edges.get(node, {}), reverse=True):
                if neighbor not in parent:
                    parent[neighbor] = node
                    stack.append(neighbor)
        return PlanningResult([], SearchTrace(expanded))
