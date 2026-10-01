"""Implement these classes, then enable their entries in agent/registry.py."""

from agent.models import DiscoveredGraphView, PlanningResult, Position


class DijkstraPlanner:
    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        # TODO: maintain best costs and parents, relax graph.edges[node].items(),
        # and return a path INCLUDING start and target. Return [] if unreachable.
        # Costs are directed: entering a node costs that node's weight.
        # Populate SearchTrace for the UI; do not read environment internals.
        raise NotImplementedError('Implement DijkstraPlanner.plan')


class AStarPlanner:
    def __init__(self, heuristic='l1'):
        self.heuristic = heuristic

    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult:
        # TODO: prioritize g + distance(node, target, self.heuristic).
        # See agent.distances.distance. MSE/squared L2 may overestimate.
        # Handle improved paths and deterministic ties; return PlanningResult.
        raise NotImplementedError('Implement AStarPlanner.plan')
