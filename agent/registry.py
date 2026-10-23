"""Selectable full-map shortest-path algorithms."""

from dataclasses import dataclass
from typing import Callable

from agent.algorithms.astar import AStar
from agent.algorithms.dijkstra import Dijkstra


@dataclass(frozen=True)
class Algorithm:
    label: str
    description: str
    factory: Callable


ALGORITHMS = {
    'dijkstra': Algorithm('Dijkstra', 'Minimum-cost search using g; heuristic is always zero.', Dijkstra),
    'astar': Algorithm('A*', 'Weighted search using g + w × h with the selected heuristic.', AStar),
}
