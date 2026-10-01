"""Basic two-dimensional simulation grid."""

from dataclasses import dataclass, field

import networkx as nx

Node = tuple[int, int]

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

    def is_walkable(self, node: Node) -> bool:
        return node in self.graph

    def neighbors(self, node: Node) -> list[Node]:
        if not self.is_walkable(node):
            raise ValueError(f"{node} est un obstacle ou hors de la grille")
        return list(self.graph.neighbors(node))