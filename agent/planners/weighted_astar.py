"""Weighted A*: f = g + w * h."""

from agent.distances import distance
from agent.planners.template import _search


class WeightedAStarPlanner:
    def __init__(self, w=1.0, heuristic='l1'):
        if w < 0:
            raise ValueError('w doit être >= 0')
        self.w = w
        self.heuristic = heuristic

    def plan(self, graph, start, target):
        return _search(graph, start, target,
                       lambda node: self.w * distance(node, target, self.heuristic))