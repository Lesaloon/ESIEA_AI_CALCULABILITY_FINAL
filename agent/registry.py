"""Add an Algorithm entry to expose a student implementation in the UI."""

from dataclasses import dataclass
from typing import Callable
from agent.algorithms.explorer import Explorer
from agent.algorithms.algo_template import AlgoPolicy
from agent.planners.breadth_first import BreadthFirstPlanner
from agent.planners.template import AStarPlanner, DijkstraPlanner
from agent.planners.depth_first import DepthFirstPlanner
from agent.planners.greedy import GreedyPlanner

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
                          lambda config: Explorer(DijkstraPlanner())),
    'astar': Algorithm('A*', 'Implement heuristic shortest-path planning.',
                       lambda config: Explorer(AStarPlanner(config.heuristic))),
    'dfs': Algorithm('Depth-first', 'Explores deep first; ignores weights, not optimal.',
                     lambda config: Explorer(DepthFirstPlanner())),
    'greedy': Algorithm('Greedy best-first', 'Follows the heuristic only; not optimal.',
                        lambda config: Explorer(GreedyPlanner(config.heuristic))),
    'template': Algorithm('Algo policy', 'Implement a complete local-observation policy.',
                         lambda config: AlgoPolicy(), enabled=False),
}
