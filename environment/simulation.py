"""Authoritative local-observation simulation, shared by HTTP and gRPC."""

import asyncio
import math
from uuid import uuid4


def distances(position: tuple[int, int], goal: tuple[int, int]) -> dict[str, float]:
    dx, dy = abs(position[0] - goal[0]), abs(position[1] - goal[1])
    squared = dx * dx + dy * dy
    return dict(l1=dx + dy, l2=math.sqrt(squared), squared_l2=squared,
                mse=squared / 2, linf=max(dx, dy))


def point(node: tuple[int, int]) -> dict[str, int]:
    return dict(x=node[0], y=node[1])


def grid_snapshot(grid):
    return dict(width=grid.width, height=grid.height,
                cells=[['empty' if grid.is_walkable((x, y)) else 'obstacle'
                        for x in range(grid.width)] for y in range(grid.height)],
                weights=[[grid.graph.nodes[x, y]['weight'] if grid.is_walkable((x, y)) else None
                          for x in range(grid.width)] for y in range(grid.height)])


class SimulationError(Exception):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


class Simulation:
    def __init__(self, grid_provider):
        self._grid = grid_provider
        self.lock = asyncio.Lock()
        self.start = None
        self.goal = None
        self.run = None
        self.start_request = None
        self.actions = {}
        self.events = []

    @property
    def active(self):
        return self.run is not None and self.run['status'] == 'active'

    def scenario(self):
        return dict(start=point(self.start) if self.start is not None else None,
                    goal=point(self.goal) if self.goal is not None else None,
                    locked=self.active)

    def configure(self, start, goal):
        if self.active:
            raise SimulationError('End the current run before editing its scenario')
        for node in (start, goal):
            if node is not None and not self._grid().is_walkable(node):
                raise SimulationError('Endpoints must be walkable and inside the grid', 422)
        self.start, self.goal = start, goal
        return self.scenario()

    def protect_obstacle(self, nodes):
        if any(node in (self.start, self.goal) for node in nodes):
            raise SimulationError('Cannot place an obstacle on the start or goal')

    def require_run(self, run_id):
        if self.run is None or self.run['run_id'] != run_id:
            raise SimulationError('Run no longer exists; reset the agent', 404)

    def _observation(self):
        run = self.run
        position, goal = run['position'], run['goal']
        grid = self._grid()
        return dict(
            run_id=run['run_id'], turn=run['turn'], position=point(position), goal=point(goal),
            current_cell_weight=grid.graph.nodes[position]['weight'],
            goal_distances=distances(position, goal), goal_reached=position == goal,
            neighbors=[dict(position=point(node), movement_cost=grid.graph.nodes[node]['weight'],
                            goal_distances=distances(node, goal))
                       for node in sorted(grid.neighbors(position))],
        )

    def observe(self):
        # Finished runs keep their last local snapshot, even if a teacher edits
        # or resizes the live grid before starting the next run.
        return self.run['observation']

    def state(self):
        return dict(run_id=self.run['run_id'], status=self.run['status'],
                    observation=self.observe(), cumulative_cost=self.run['cost'],
                    start=point(self.run['start']))

    def start_run(self, request_id):
        if not request_id:
            raise SimulationError('A start request ID is required', 422)
        if self.start_request == request_id and self.run is not None:
            return self.state()
        if self.active:
            raise SimulationError('Another run is already active')
        if self.start is None or self.goal is None:
            raise SimulationError('Configure both start and goal first', 422)
        self.run = dict(run_id=str(uuid4()), start=self.start, goal=self.goal,
                        position=self.start, turn=0, cost=0,
                        status='succeeded' if self.start == self.goal else 'active')
        self.start_request = request_id
        self.actions, self.events = {}, []
        self.run['observation'] = self._observation()
        self.run['grid_snapshot'] = grid_snapshot(self._grid())
        return self.state()

    def apply(self, run_id, expected_turn, action_id, target=None, stop_reason=None):
        self.require_run(run_id)
        fingerprint = (expected_turn, target, stop_reason)
        if action_id in self.actions:
            previous, event = self.actions[action_id]
            if previous != fingerprint:
                raise SimulationError('Action ID reused with a different action')
            return event
        if not action_id:
            raise SimulationError('An action ID is required', 422)
        if not self.active or expected_turn != self.run['turn']:
            raise SimulationError('Run is finished or the expected turn is stale')
        if target is None and stop_reason is None:
            raise SimulationError('An action is required', 422)
        origin = self.run['position']
        cost = 0
        if target is not None:
            if target not in self._grid().neighbors(origin):
                raise SimulationError('Move must target a current walkable neighbor', 422)
            cost = self._grid().graph.nodes[target]['weight']
            self.run['position'] = target
            self.run['cost'] += cost
            if target == self.run['goal']:
                self.run['status'] = 'succeeded'
        else:
            self.run['status'] = 'stopped'
        self.run['turn'] += 1
        self.run['observation'] = self._observation()
        event = dict(sequence=len(self.events) + 1, turn=self.run['turn'],
                     **{'from': point(origin), 'to': point(self.run['position'])},
                     action='move' if target is not None else 'stop', step_cost=cost,
                     cumulative_cost=self.run['cost'], observation=self.observe(),
                     reason=stop_reason or '')
        self.events.append(event)
        self.actions[action_id] = (fingerprint, event)
        return event

    def end(self, run_id):
        self.require_run(run_id)
        if self.active:
            self.run['status'] = 'stopped'
        return self.state()
