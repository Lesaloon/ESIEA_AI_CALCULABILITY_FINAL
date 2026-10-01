"""Explore unseen cells and replan after every actual move."""

from agent.distances import distance
from agent.models import Decision, Move, SearchTrace, Stop


class Explorer:
    def __init__(self, planner, commit=False):
        self.planner = planner
        # Follow each planned route to its target before replanning. Needed for
        # planners whose route changes from one cell to the next (DFS, greedy),
        # which would otherwise oscillate between two cells forever.
        self.commit = commit

    def reset(self, config):
        self.config = config
        self.route = []

    def decide(self, observation, knowledge):
        if observation.goal_reached:
            return Decision(Stop('Goal reached'))
        if self.commit and self._can_continue(observation, knowledge):
            self.route = self.route[1:]
            return Decision(Move(self.route[0]), f'Continue planned route toward {self.route[-1]}.',
                            SearchTrace(candidate_path=[observation.position, *self.route]))
        candidates = knowledge.weights.keys() - knowledge.visited
        if observation.goal in knowledge.weights:
            candidates = [observation.goal]
        else:
            candidates = sorted(candidates, key=lambda p: (
                distance(p, observation.goal, self.config.heuristic), p))
        for target in candidates:
            result = self.planner.plan(knowledge, observation.position, target)
            if len(result.path) > 1:
                self.route = result.path[1:]
                return Decision(Move(result.path[1]),
                                f'Route toward {target}; reveal neighbors after one move.', result.trace)
        return Decision(Stop('Reachable component explored; no route to the goal'),
                        'No unvisited reachable cell remains.')

    def _can_continue(self, observation, knowledge):
        """The agent is on its route, the next step is known, and no goal detour is due."""
        route = self.route
        if len(route) < 2 or route[0] != observation.position:
            return False
        if observation.goal in knowledge.weights and route[-1] != observation.goal:
            return False
        return route[1] in knowledge.edges.get(observation.position, {})
