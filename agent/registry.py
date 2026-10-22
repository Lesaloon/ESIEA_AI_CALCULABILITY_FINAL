"""Selectable full-map shortest-path algorithms."""

from dataclasses import dataclass
from typing import Callable

from agent.algorithms.astar import AStar
from agent.algorithms.dijkstra import Dijkstra
from agent.algorithms.weighted_astar import WeightedAStar


@dataclass(frozen=True)
class Algorithm:
    label: str
    description: str
    factory: Callable


ALGORITHMS = {
    'dijkstra': Algorithm('Dijkstra', 'Minimum-cost search using g; heuristic is always zero.', Dijkstra),
    'astar': Algorithm('A*', 'Weighted search using g + h with the selected heuristic.', AStar),
    'weighted_astar': Algorithm('Weighted A*', 'A* ordered by g + w·h. w defaults to 1.', WeightedAStar),
}
