"""Runnable scaffolding: shortest-hop paths, deliberately ignoring weights."""

from collections import deque
from agent.models import PlanningResult, SearchTrace


class BreadthFirstPlanner:
    def plan(self, graph, start, target):
        queue = deque([start])
        parent = {start: None}
        expanded = []
        while queue:
            node = queue.popleft()
            expanded.append(node)
            if node == target:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return PlanningResult(path, SearchTrace(expanded, list(queue), path))
            for neighbor in sorted(graph.edges.get(node, {})):
                if neighbor not in parent:
                    parent[neighbor] = node
                    queue.append(neighbor)
        return PlanningResult([], SearchTrace(expanded))
