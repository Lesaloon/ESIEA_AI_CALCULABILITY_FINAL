"""Execute a selected algorithm's route without physical exploration."""

from agent.models import Decision, Move, SearchTrace, Stop
from agent.registry import ALGORITHMS, OPTIMIZERS


class Agent:
    def reset(self, config):
        self.config = config
        self.algorithm = ALGORITHMS[config.algorithm].factory(config.heuristic, config.weight)
        self.optimizer = OPTIMIZERS[config.optimizer](config.optimizer_params) if config.optimizer != 'none' else None
        self.path = None
        self.explanation = 'Follow the computed route to the goal.'

    def tune(self, knowledge, start, goal):
        """Let the optimizer pick the A* heuristic and weight; returns the report for the trace."""
        heuristic, weight, trials, reference = self.optimizer.tune(
            knowledge, start, goal, self.config.heuristic, self.config.weight)
        self.algorithm = ALGORITHMS['astar'].factory(heuristic, weight)
        best = next(t for t in trials if (t['heuristic'], t['weight']) == (heuristic, round(weight, 3)))
        self.explanation = (f'{self.optimizer.label} chose heuristic {heuristic} with weight {weight:g} '
                            f'after {len(trials)} trials; following the computed route.')
        return dict(optimizer=self.config.optimizer, label=self.optimizer.label, params=self.optimizer.values,
                    heuristic=heuristic, weight=weight, score=best['score'], best=best,
                    reference=reference, trials=trials)

    def decide(self, observation, knowledge):
        if self.path is None:
            tuning = self.tune(knowledge, observation.position, observation.goal) if self.optimizer else None
            result = self.algorithm.search(knowledge, observation.position, observation.goal)
            self.path = result.path
            trace = result.trace
            trace.tuning = tuning
        else:
            trace = SearchTrace()
        if observation.goal_reached:
            return Decision(Stop('Goal reached'), 'The agent has reached the goal.', trace)
        if not self.path:
            return Decision(Stop('No route to the goal'), 'The goal is unreachable on the frozen map.', trace)
        step = self.path.index(observation.position)
        trace.candidate_path = self.path[step:]
        return Decision(Move(self.path[step + 1]), self.explanation, trace)
