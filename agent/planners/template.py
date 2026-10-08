"""Weighted shortest-path planners for the discovered graph."""

import heapq

from agent.distances import distance
from agent.models import DiscoveredGraphView, PlanningResult, Position, SearchTrace


class DijkstraPlanner:
    """Find minimum-cost paths with Dijkstra's shortest-path algorithm."""

    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        # 1. Initialisation
        heap = [(0, start)]
        best = {start: 0}
        parent = {start: None}
        settled = set()
        expanded = []

        while heap:
            # 2. Extraction du nœud le moins cher
            cost, node = heapq.heappop(heap)
            if node in settled:
                continue

            # 3. Coût du nœud devenu définitif
            settled.add(node)
            expanded.append(node)

            # 4. Test de la cible et reconstruction du chemin
            if node == target:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return PlanningResult(path, self._trace(heap, best, settled, expanded, path))

            # 5. Relaxation des arêtes sortantes
            for neighbor, step in graph.edges.get(node, {}).items():
                new_cost = cost + step
                if neighbor not in best or new_cost < best[neighbor]:
                    best[neighbor] = new_cost
                    parent[neighbor] = node
                    heapq.heappush(heap, (new_cost, neighbor))

        # 6. Échec
        return PlanningResult([], SearchTrace(expanded))

    def _trace(self, heap, best, settled, expanded, path):
        waiting = {}
        for _, node in sorted(heap):
            if node not in settled and node not in waiting:
                waiting[node] = best[node]
        scores = [{'x': x, 'y': y, 'g': g} for (x, y), g in waiting.items()]
        return SearchTrace(expanded, list(waiting), path, scores)


class AStarPlanner:
    """Find weighted paths with A* and a configurable distance heuristic."""

    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        # 1. Initialisation
        h_start = distance(start, target, self.heuristic)
        heap = [(h_start, h_start, start, 0)]
        best = {start: 0}
        parent = {start: None}
        expanded = []

        while heap:
            # 2. Extraction du nœud de plus petit f
            _, _, node, g = heapq.heappop(heap)
            if g > best[node]:
                continue

            # 3. Expansion du nœud
            expanded.append(node)

            # 4. Test de la cible et reconstruction du chemin
            if node == target:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return PlanningResult(path, self._trace(heap, best, expanded, path))

            # 5. Relaxation avec f = g + h
            for neighbor, step in graph.edges.get(node, {}).items():
                new_g = g + step
                if neighbor not in best or new_g < best[neighbor]:
                    best[neighbor] = new_g
                    parent[neighbor] = node
                    h = distance(neighbor, target, self.heuristic)
                    heapq.heappush(heap, (new_g + h, h, neighbor, new_g))

        # 6. Échec
        return PlanningResult([], SearchTrace(expanded))

    def _trace(self, heap, best, expanded, path):
        waiting = {}
        for f, h, node, g in sorted(heap):
            if g == best[node] and node not in waiting:
                waiting[node] = {'x': node[0], 'y': node[1], 'g': g, 'h': h, 'f': f}
        return SearchTrace(expanded, list(waiting), path, list(waiting.values()))
