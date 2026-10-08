"""Depth-first search: dive along one branch, backtrack only at dead ends.
Finds *a* path, not the shortest one, and ignores weights."""

from agent.models import PlanningResult, SearchTrace


class DepthFirstPlanner:
    def plan(self, graph, start, target):
        # 1. Initialisation
        stack = [(start, None)]
        parent = {}
        expanded = []

        while stack:
            # 2. Dépilement du nœud courant
            node, came_from = stack.pop()
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
                frontier = list(dict.fromkeys(n for n, _ in stack if n not in parent))
                return PlanningResult(path, SearchTrace(expanded, frontier, path))

            # 5. Empilement des voisins
            for neighbor in sorted(graph.edges.get(node, {}), reverse=True):
                if neighbor not in parent:
                    stack.append((neighbor, node))

        # 6. Échec
        return PlanningResult([], SearchTrace(expanded))
