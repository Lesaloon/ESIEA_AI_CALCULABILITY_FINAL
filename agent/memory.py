"""Read-only frozen run graph and physical visit tracking."""

from types import MappingProxyType
from agent.models import GraphView


class RunGraph:
    """Load all walkable cells once; observations only record visits."""

    def __init__(self):
        self.edges = {}
        self.weights = {}
        self.visited = set()

    def observe(self, observation):
        self.visited.add(observation.position)

    def seed(self, snapshot):
        weights = {(cell['position']['x'], cell['position']['y']): cell['weight']
                   for cell in snapshot['walkable_cells']}
        self.weights.update(weights)
        for node in weights:
            self.edges.setdefault(node, {})
            x, y = node
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    neighbor = (x + dx, y + dy)
                    if neighbor != node and neighbor in weights:
                        self.edges[node][neighbor] = weights[neighbor]

    def view(self):
        return GraphView(
            MappingProxyType({node: MappingProxyType(dict(edges)) for node, edges in self.edges.items()}),
            MappingProxyType(dict(self.weights)), frozenset(self.visited))

    def snapshot(self):
        return [dict(x=node[0], y=node[1], weight=weight, visited=node in self.visited)
                for node, weight in sorted(self.weights.items())]
