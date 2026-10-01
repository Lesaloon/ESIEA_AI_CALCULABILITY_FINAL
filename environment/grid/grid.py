"""Basic two-dimensional simulation grid."""

import random
from dataclasses import dataclass, field

import networkx as nx


@dataclass
class Grid:
    """A non-periodic graph of (x, y) nodes with four-way connectivity."""

    width: int
    height: int
    graph: nx.Graph = field(init=False)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Grid dimensions must be positive")

        self.graph = nx.grid_2d_graph(self.width, self.height)

    def remove_node(self, node: tuple[int, int]) -> None:
        """Remove a node and every edge connected to it."""
        if node not in self.graph:
            raise ValueError(f"Node {node} is not in the grid")
        self.graph.remove_node(node)

    def create_obstacles(self, count: int) -> list[tuple[int, int]]:
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