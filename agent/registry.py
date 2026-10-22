"""Selectable full-map shortest-path algorithms and parameter optimizers."""

from dataclasses import dataclass
from typing import Callable

from agent.algorithms.astar import AStar
from agent.algorithms.dijkstra import Dijkstra
from agent.algorithms.greedy import Greedy
from agent.algorithms.optimizers import GridSearch, HillClimbing, RandomSearch, SimulatedAnnealing, TabuSearch


@dataclass(frozen=True)
class Algorithm:
    label: str
    description: str
    factory: Callable


ALGORITHMS = {
    'dijkstra': Algorithm('Dijkstra', 'Minimum-cost search using g; heuristic is always zero.', Dijkstra),
    'astar': Algorithm('Weighted A*', 'Search using f = g + w·h; w = 1 is classic A*, w > 1 is faster but may be suboptimal.', AStar),
    'greedy': Algorithm('Greedy best-first', 'Search using f = h only: fast, ignores the cost already paid, not optimal.',
                        Greedy),
}

# Optimizers tune (heuristic, weight) for A*. The UI builds its form from `params`.
OPTIMIZERS = {
    'grid': GridSearch,
    'random': RandomSearch,
    'hill_climbing': HillClimbing,
    'simulated_annealing': SimulatedAnnealing,
    'tabu': TabuSearch,
}
