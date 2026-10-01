"""Transport-independent types exposed to student code."""

from dataclasses import dataclass, field
from typing import Mapping, Protocol

Position = tuple[int, int]


@dataclass(frozen=True)
class Neighbor:
    position: Position
    movement_cost: float
    goal_distances: Mapping[str, float]


@dataclass(frozen=True)
class Observation:
    run_id: str
    turn: int
    position: Position
    goal: Position
    current_cell_weight: float
    goal_distances: Mapping[str, float]
    neighbors: tuple[Neighbor, ...]
    goal_reached: bool


@dataclass(frozen=True)
class AgentConfig:
    heuristic: str = 'l1'


@dataclass(frozen=True)
class DiscoveredGraphView:
    """Only observed nodes; costs are directional destination-cell weights."""
    edges: Mapping[Position, Mapping[Position, float]]
    weights: Mapping[Position, float]
    visited: frozenset[Position]


@dataclass(frozen=True)
class Move:
    target: Position


@dataclass(frozen=True)
class Stop:
    reason: str


@dataclass
class SearchTrace:
    expanded: list[Position] = field(default_factory=list)
    frontier: list[Position] = field(default_factory=list)
    candidate_path: list[Position] = field(default_factory=list)
    scores: list[dict] = field(default_factory=list)


@dataclass
class PlanningResult:
    path: list[Position]
    trace: SearchTrace = field(default_factory=SearchTrace)


@dataclass
class Decision:
    action: Move | Stop
    explanation: str = ''
    trace: SearchTrace = field(default_factory=SearchTrace)


class AgentPolicy(Protocol):
    def reset(self, config: AgentConfig) -> None: ...
    def decide(self, observation: Observation, knowledge: DiscoveredGraphView) -> Decision: ...


class PathPlanner(Protocol):
    def plan(self, graph: DiscoveredGraphView, start: Position, target: Position) -> PlanningResult: ...
