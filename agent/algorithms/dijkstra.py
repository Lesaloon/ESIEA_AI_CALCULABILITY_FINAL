"""Dijkstra uses the shared weighted search with priority g alone."""

from agent.algorithms.astar import AStar


class Dijkstra(AStar):
    def __init__(self, heuristic='zero', weight=1.0):
        super().__init__('zero', 1.0)

    def estimate(self, node, target):
        return 0.0
