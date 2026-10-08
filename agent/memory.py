"""Build read-only graph views from observations or an opted-in grid snapshot."""

from types import MappingProxyType
from agent.models import DiscoveredGraphView


class DiscoveredGraph:
    """Accumulate a graph using only cells observed by the agent."""

    def __init__(self):
        self.edges = {}
        self.weights = {}
        self.visited = set()

    def observe(self, observation):
        current = observation.position
        self.visited.add(current)
        self.weights[current] = observation.current_cell_weight
        self.edges.setdefault(current, {})
        for neighbor in observation.neighbors:
            node = neighbor.position
            self.weights[node] = neighbor.movement_cost
            self.edges[current][node] = neighbor.movement_cost
            # Four-way connectivity is symmetric, but movement costs are not.
            self.edges.setdefault(node, {})[current] = observation.current_cell_weight

    def seed(self, snapshot):
        weights = {(cell['position']['x'], cell['position']['y']): cell['weight']
                   for cell in snapshot['walkable_cells']}
        self.weights.update(weights)
        for node in weights:
            self.edges.setdefault(node, {})
            x, y = node
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in weights:
                    self.edges[node][neighbor] = weights[neighbor]

    def view(self):
        return DiscoveredGraphView(
            MappingProxyType({node: MappingProxyType(dict(edges)) for node, edges in self.edges.items()}),
            MappingProxyType(dict(self.weights)), frozenset(self.visited))

    def snapshot(self):
        return [dict(x=node[0], y=node[1], weight=weight, visited=node in self.visited)
                for node, weight in sorted(self.weights.items())]
