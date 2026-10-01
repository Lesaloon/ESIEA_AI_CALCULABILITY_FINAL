"""Basic two-dimensional simulation grid."""

import random
from dataclasses import dataclass, field

import networkx as nx

Node = tuple[int, int]

@dataclass
class Grid:
    """A non-periodic graph of (x, y) nodes with four-way connectivity."""

    width: int
    height: int
    graph: nx.Graph = field(init=False)
    _removed_weights: dict[Node, float] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Grid dimensions must be positive")

        self.graph = nx.grid_2d_graph(self.width, self.height)
        nx.set_node_attributes(self.graph, 1, "weight")

    def is_walkable(self, node: Node) -> bool:
        return node in self.graph

    @staticmethod
    def _validate_weight(weight: int) -> None:
        if type(weight) is not int or not 1 <= weight <= 9:
            raise ValueError("Weight must be an integer between 1 and 9")

    def set_weight(self, node: Node, weight: int) -> None:
        self._validate_weight(weight)
        x, y = node
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError("Coordinates are outside the grid")
        if not self.is_walkable(node):
            raise ValueError("Cannot set the weight of an obstacle")
        self.graph.nodes[node]["weight"] = weight

    def set_all_weights(self, weight: int) -> None:
        """Update walkable cells, preserving saved weights beneath obstacles."""
        self._validate_weight(weight)
        nx.set_node_attributes(self.graph, weight, "weight")

    def reset_weights(self) -> None:
        """Reset visible and saved weights without changing the topology."""
        self.set_all_weights(1)
        self._removed_weights = dict.fromkeys(self._removed_weights, 1)

    def neighbors(self, node: Node) -> list[Node]:
        if not self.is_walkable(node):
            raise ValueError(f"{node} est un obstacle ou hors de la grille")
        return list(self.graph.neighbors(node))
    
    def remove_node(self, node: Node) -> None:
        """Remove a node and every edge connected to it."""
        if node not in self.graph:
            raise ValueError(f"Node {node} is not in the grid")
        self._removed_weights[node] = self.graph.nodes[node]["weight"]
        self.graph.remove_node(node)

    def add_node(self, node: Node) -> None:
        """Restore a cell and its edges to existing four-way neighbors."""
        x, y = node
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError("Coordinates are outside the grid")
        if node in self.graph:
            raise ValueError(f"Node {node} is already in the grid")
        self.graph.add_node(node, weight=self._removed_weights.pop(node, 1))
        for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if neighbor in self.graph:
                self.graph.add_edge(node, neighbor)

    def create_obstacles(self, count: int) -> list[Node]:
        """Remove `count` random nodes and return their coordinates."""
        if count < 0:
            raise ValueError("Obstacle count must be positive")
        nodes = list(self.graph.nodes)
        if count > len(nodes):
            raise ValueError("Obstacle count exceeds the number of nodes")
        obstacles_coord = random.sample(nodes, count)
        for node in obstacles_coord:
            self.remove_node(node)
        return obstacles_coord
