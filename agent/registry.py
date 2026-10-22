"""Selectable full-map shortest-path algorithms."""

from dataclasses import dataclass
from typing import Callable

from agent.algorithms.astar import AStar
from agent.algorithms.breadth_first import BreadthFirst
from agent.algorithms.depth_first import DepthFirst
from agent.algorithms.dijkstra import Dijkstra
from agent.algorithms.greedy import Greedy


@dataclass(frozen=True)
class Algorithm:
    label: str
    description: str
    factory: Callable
    weighted: bool = False  # factory also takes the run's w


ALGORITHMS = {
    'bfs': Algorithm('BFS', 'Fewest moves; ignores weights and the heuristic.', BreadthFirst),
    'dfs': Algorithm('DFS', 'Follows one branch as deep as possible; ignores weights and the heuristic.',
                     DepthFirst),
    'greedy': Algorithm('Greedy best-first', 'Expands the cell that looks closest to the goal (h only).',
                        Greedy),
    'dijkstra': Algorithm('Dijkstra', 'Minimum-cost search using g; heuristic is always zero.', Dijkstra),
    'astar': Algorithm('A*', 'Weighted search using g + h with the selected heuristic.', AStar),
    'weighted_astar': Algorithm('Weighted A*', 'g + w·h: faster as w grows, at most w times the optimal cost '
                                'with an admissible heuristic.', AStar, weighted=True),
}
