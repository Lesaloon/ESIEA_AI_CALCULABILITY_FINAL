"""Add an Algorithm entry to expose a student implementation in the UI."""

from dataclasses import dataclass
from typing import Callable
from agent.algorithms.explorer import Explorer
from agent.algorithms.algo_template import AlgoPolicy
from agent.planners.breadth_first import BreadthFirstPlanner
from agent.planners.depth_first import DepthFirstPlanner
from agent.planners.greedy_best_first import GreedyBestFirstPlanner
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
    'dfs': Algorithm('Explorer · depth-first',
                     'Follows one branch as deep as possible; finds a route, rarely the shortest; ignores weights.',
                     lambda config: Explorer(DepthFirstPlanner(), commit=True)),
    'greedy': Algorithm('Explorer · greedy best-first',
                        'Expands the cell closest to the target by heuristic; fast, ignores weights.',
                        lambda config: Explorer(GreedyBestFirstPlanner(config.heuristic), commit=True)),
    'dijkstra': Algorithm('Explorer · Dijkstra',
                          'Minimum-cost planning on discovered cells, using cell weights.',
                          lambda config: Explorer(DijkstraPlanner())),
    'astar': Algorithm('Explorer · A*',
                       'Dijkstra guided by the selected heuristic toward the target.',
                       lambda config: Explorer(AStarPlanner(config.heuristic))),
    'template': Algorithm('Algo policy', 'Implement a complete local-observation policy.',
                         lambda config: AlgoPolicy(), enabled=False),
}
