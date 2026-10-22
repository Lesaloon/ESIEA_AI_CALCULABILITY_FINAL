"""Execute a selected algorithm's route without physical exploration."""

from agent.models import Decision, Move, SearchTrace, Stop
from agent.registry import ALGORITHMS


class Agent:
    def reset(self, config):
        self.config = config
        entry = ALGORITHMS[config.algorithm]
        self.algorithm = (entry.factory(config.heuristic, config.weight) if entry.weighted
                          else entry.factory(config.heuristic))
        self.path = None

    def decide(self, observation, knowledge):
        if self.path is None:
            result = self.algorithm.search(knowledge, observation.position, observation.goal)
            self.path = result.path
            trace = result.trace
        else:
            trace = SearchTrace()
        if observation.goal_reached:
            return Decision(Stop('Goal reached'), 'The agent has reached the goal.', trace)
        if not self.path:
            return Decision(Stop('No route to the goal'), 'The goal is unreachable on the frozen map.', trace)
        step = self.path.index(observation.position)
        trace.candidate_path = self.path[step:]
        return Decision(Move(self.path[step + 1]), 'Follow the computed route to the goal.', trace)
