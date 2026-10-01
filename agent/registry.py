"""Add an Algorithm entry to expose a student implementation in the UI."""

from dataclasses import dataclass
from typing import Callable
from agent.algorithms.explorer import Explorer
from agent.algorithms.algo_template import AlgoPolicy
from agent.planners.breadth_first import BreadthFirstPlanner
from agent.planners.template import AStarPlanner, DijkstraPlanner


@dataclass(frozen=True)
class Algorithm:
    label: str
    description: str
    factory: Callable
    enabled: bool = True


ALGORITHMS = {
    'example': Algorithm('Example explorer · breadth-first',
                         'Shortest-hop planning on discovered cells; ignores weights.',
                         lambda config: Explorer(BreadthFirstPlanner())),
    'dijkstra': Algorithm('Dijkstra', 'Implement the weighted shortest-path planner.',
                          lambda config: Explorer(DijkstraPlanner()), enabled=False),
    'astar': Algorithm('A*', 'Implement heuristic shortest-path planning.',
                       lambda config: Explorer(AStarPlanner(config.heuristic)), enabled=False),
    'template': Algorithm('Algo policy', 'Implement a complete local-observation policy.',
                         lambda config: AlgoPolicy(), enabled=False),
}
