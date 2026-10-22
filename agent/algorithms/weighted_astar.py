"""Weighted A*: same search as A*, ordered by g + w * h."""

from agent.algorithms.astar import AStar


class WeightedAStar(AStar):
    def __init__(self, heuristic='l1', w=1.0):
        super().__init__(heuristic)
        self.w = w

    def priority(self, cost, heuristic):
        return cost + self.w * heuristic
