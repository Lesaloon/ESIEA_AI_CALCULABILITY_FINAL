"""A* shortest paths. Priority is the path cost plus a geometric heuristic."""

from agent.models import DiscoveredGraphView, PlanningResult, Position
from agent.planners.dijkstra import weighted_search


class AStarPlanner:
    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        return weighted_search(graph, start, target, self.heuristic)
