"""Dijkstra uses the shared weighted search with priority g alone."""

from agent.algorithms.astar import AStar


class Dijkstra(AStar):
    """Find minimum-cost routes by expanding the lowest accumulated cost first."""

    def __init__(self, heuristic='zero', heuristic_weight=1.0):
        # Accept the shared factory arguments, but ignore heuristic settings.
        super().__init__('zero')

    def estimate(self, node, target):
        # With h = 0, the inherited A* priority becomes f = g.
        return 0.0
