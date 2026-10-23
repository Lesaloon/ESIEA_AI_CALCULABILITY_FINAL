"""Execute a selected algorithm's route without physical exploration."""

from agent.models import Decision, Move, SearchTrace, Stop
from agent.registry import ALGORITHMS


class Agent:
    """Plan once on the known map, then execute one route edge per decision."""

    def reset(self, config):
        """Select the search algorithm and discard the previous run's route."""
        self.config = config
        self.algorithm = ALGORITHMS[config.algorithm].factory(config.heuristic, config.heuristic_weight)
        self.path = None

    def decide(self, observation, knowledge):
        """Return the next move or a stop decision, with visualization data."""
        if self.path is None:
            # None means not planned yet; [] means planning found no route.
            result = self.algorithm.search(knowledge, observation.position, observation.goal)
            self.path = result.path
            trace = result.trace
        else:
            # Only the first decision carries the full search expansion trace.
            trace = SearchTrace()
        if observation.goal_reached:
            return Decision(Stop('Goal reached'), 'The agent has reached the goal.', trace)
        if not self.path:
            return Decision(Stop('No route to the goal'), 'The goal is unreachable on the frozen map.', trace)
        step = self.path.index(observation.position)
        # Show only the untraveled route while reusing the original plan.
        trace.candidate_path = self.path[step:]
        return Decision(Move(self.path[step + 1]), 'Follow the computed route to the goal.', trace)
