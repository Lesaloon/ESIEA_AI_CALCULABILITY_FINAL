"""Optional exercise: implement an entire local-observation policy."""

from agent.models import AgentConfig, Decision, DiscoveredGraphView, Observation


class AlgoPolicy:
    def reset(self, config: AgentConfig) -> None:
        self.config = config
        # Initialize private state here. reset() is called for each new run.

    def decide(self, observation: Observation, knowledge: DiscoveredGraphView) -> Decision:
        # Return Move to an observation.neighbors position, or Stop(reason).
        # You may remember observations; you cannot inspect distant cells.
        raise NotImplementedError('Implement AlgoPolicy.decide')
