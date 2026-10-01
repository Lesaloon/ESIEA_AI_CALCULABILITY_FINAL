"""Greedy best-first search. Priority is the heuristic alone, not the path cost."""

import heapq

from agent.distances import distance
from agent.models import PlanningResult, SearchTrace


class GreedyBestFirstPlanner:
    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def plan(self, graph, start, target):
        def h(node):
            return distance(node, target, self.heuristic)

        heap = [(h(start), start)]
        parent = {start: None}
        g_score = {start: 0.0}
        expanded = []
        settled = set()
        while heap:
            _priority, node = heapq.heappop(heap)
            if node in settled:
                continue
            settled.add(node)
            expanded.append(node)
            if node == target:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                scores = [{'x': cell[0], 'y': cell[1], 'g': g_score[cell],
                           'h': h(cell), 'f': h(cell)} for cell in sorted(g_score)]
                frontier = [cell for _priority, cell in sorted(heap) if cell not in settled]
                return PlanningResult(path, SearchTrace(expanded, frontier, path, scores))
            for neighbor in sorted(graph.edges.get(node, {})):
                if neighbor in parent:
                    continue
                parent[neighbor] = node
                g_score[neighbor] = g_score[node] + graph.edges[node][neighbor]
                heapq.heappush(heap, (h(neighbor), neighbor))
        return PlanningResult([], SearchTrace(expanded))
