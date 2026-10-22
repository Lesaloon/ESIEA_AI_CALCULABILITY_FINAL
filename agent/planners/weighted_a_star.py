import heapq

from agent.distances import distance
from agent.models import DiscoveredGraphView, PlanningResult, Position, SearchTrace

class WeightedAStarPlanner:
    """Find weighted paths with weighted A* (f = g + w * h)."""

    def __init__(self, heuristic='l1', weight=1.5):
        if weight < 1:
            raise ValueError("weight doit être >= 1 pour conserver la borne de sous-optimalité")
        self.heuristic = heuristic
        self.weight = weight

    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        # 1. Initialisation
        h_start = distance(start, target, self.heuristic)
        heap = [(self.weight * h_start, h_start, start, 0)]
        best = {start: 0}
        parent = {start: None}
        expanded = []

        while heap:
            # 2. Extraction du nœud de plus petit f = g + w*h
            _, _, node, g = heapq.heappop(heap)
            if g > best[node]:
                continue  # entrée périmée : un meilleur g a été trouvé depuis

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

            # 5. Relaxation avec f = g + w * h
            for neighbor, step in graph.edges.get(node, {}).items():
                new_g = g + step
                if neighbor not in best or new_g < best[neighbor]:
                    best[neighbor] = new_g
                    parent[neighbor] = node
                    h = distance(neighbor, target, self.heuristic)
                    heapq.heappush(heap, (new_g + self.weight * h, h, neighbor, new_g))

        # 6. Échec
        return PlanningResult([], SearchTrace(expanded))

    def _trace(self, heap, best, expanded, path):
            waiting = {}
            for f, h, node, g in sorted(heap):
                if g == best[node] and node not in waiting:
                    waiting[node] = {'x': node[0], 'y': node[1], 'g': g, 'h': h, 'f': f}
            return SearchTrace(expanded, list(waiting), path, list(waiting.values()))