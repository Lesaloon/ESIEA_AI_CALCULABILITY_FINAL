"""Selectable pathfinding algorithms."""

from dataclasses import dataclass
from typing import Callable

from agent.algorithms.explorer import Explorer
from agent.planners.astar import AStarPlanner
from agent.planners.breadth_first import BreadthFirstPlanner
from agent.planners.depth_first import DepthFirstPlanner
from agent.planners.dijkstra import DijkstraPlanner
from agent.planners.greedy import GreedyBestFirstPlanner


@dataclass(frozen=True)
class Algorithm:
    label: str
    description: str
    factory: Callable
    enabled: bool = True


ALGORITHMS = {
    'bfs': Algorithm(
        'BFS',
        'Breadth-first search: fewest steps, ignores edge weights.',
        lambda config: Explorer(BreadthFirstPlanner())),
    'dfs': Algorithm(
        'DFS',
        'Depth-first search: follows one branch before backtracking, ignores edge weights.',
        lambda config: Explorer(DepthFirstPlanner())),
    'greedy': Algorithm(
        'Greedy best-first',
        'Expands the discovered cell closest to the target according to the selected heuristic.',
        lambda config: Explorer(GreedyBestFirstPlanner(config.heuristic))),
    'dijkstra': Algorithm(
        'Dijkstra',
        'Weighted shortest path. The selected heuristic is not used.',
        lambda config: Explorer(DijkstraPlanner())),
    'astar': Algorithm(
        'A*',
        'Weighted shortest path guided by the selected heuristic.',
        lambda config: Explorer(AStarPlanner(config.heuristic))),
}
