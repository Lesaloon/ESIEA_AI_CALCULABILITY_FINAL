"""Explore unseen cells and replan after every actual move."""

from agent.distances import distance
from agent.models import Decision, Move, Stop


class Explorer:
    def __init__(self, planner):
        self.planner = planner

    def reset(self, config):
        self.config = config

    def decide(self, observation, knowledge):
        if observation.goal_reached:
            return Decision(Stop('Goal reached'))
        candidates = knowledge.weights.keys() - knowledge.visited
        if observation.goal in knowledge.weights:
            candidates = [observation.goal]
        else:
            candidates = sorted(candidates, key=lambda p: (
                distance(p, observation.goal, self.config.heuristic), p))
        for target in candidates:
            result = self.planner.plan(knowledge, observation.position, target)
            if len(result.path) > 1:
                return Decision(Move(result.path[1]),
                                f'Route toward {target}; reveal neighbors after one move.', result.trace)
        return Decision(Stop('Reachable component explored; no route to the goal'),
                        'No unvisited reachable cell remains.')
