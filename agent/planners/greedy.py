"""Greedy best-first search: always expand the cell that looks closest to the target.
Uses only the heuristic h(node, target); never reads edge costs. Fast, not optimal."""

import heapq

from agent.distances import distance
from agent.models import PlanningResult, SearchTrace


class GreedyPlanner:
    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def plan(self, graph, start, target):
        # 1. Initialisation
        heap = [(distance(start, target, self.heuristic), start, None)]
        parent = {}
        expanded = []

        while heap:
            # 2. Extraction du nœud le plus prometteur
            _, node, came_from = heapq.heappop(heap)
            if node in parent:
                continue

            # 3. Marquage comme visité
            parent[node] = came_from
            expanded.append(node)

            # 4. Test de la cible et reconstruction du chemin
            if node == target:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return PlanningResult(path, self._trace(heap, parent, expanded, path))

            # 5. Insertion des voisins avec leur priorité
            for neighbor in graph.edges.get(node, {}):
                if neighbor not in parent:
                    h = distance(neighbor, target, self.heuristic)
                    heapq.heappush(heap, (h, neighbor, node))

        # 6. Échec
        return PlanningResult([], SearchTrace(expanded))

    def _trace(self, heap, parent, expanded, path):
        waiting = {}
        for h, node, _ in sorted(heap):
            if node not in parent and node not in waiting:
                waiting[node] = h
        scores = [{'x': x, 'y': y, 'h': h} for (x, y), h in waiting.items()]
        return SearchTrace(expanded, list(waiting), path, scores)
