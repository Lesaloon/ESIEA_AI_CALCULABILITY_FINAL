"""Serialized turns, background execution, and replayable student traces."""

import asyncio
import json
from uuid import uuid4

import grpc
from agent.environment_client import observation_from
from agent.memory import DiscoveredGraph
from agent.models import AgentConfig, Move, Stop
from agent.registry import ALGORITHMS


class RunnerError(Exception):
    pass


def trace_dict(trace):
    def points(values):
        return [dict(x=x, y=y) for x, y in values]
    return dict(expanded=points(trace.expanded), frontier=points(trace.frontier),
                candidate_path=points(trace.candidate_path), scores=trace.scores)


class Runner:
    def __init__(self, client):
        self.client = client
        self.lock = asyncio.Lock()
        self.task = None
        self.continuous = False
        self.state = None
        self.status = 'ready'
        self.error = ''
        self.history = []
        self.memory = DiscoveredGraph()
        self.pending = None
        self.config = None
        self.initial_observation = None

    def snapshot(self):
        return dict(status=self.status, error=self.error, run=self.state,
                    initial_observation=self.initial_observation,
                    config=self.config, knowledge=self.memory.snapshot(), history_count=len(self.history))

    async def create(self, config):
        if self.continuous:
            raise RunnerError('Pause before resetting the run')
        async with self.lock:
            if self.continuous:
                raise RunnerError('Pause before resetting the run')
            agent_config = AgentConfig(config['heuristic'])
            try:
                policy = ALGORITHMS[config['algorithm']].factory(agent_config)
                policy.reset(agent_config)
            except Exception as exc:
                raise RunnerError(f'{type(exc).__name__}: {exc}') from exc
            await self.end_environment_run()
            state = await self.client.start(str(uuid4()))
            self.config, self.policy, self.state = config, policy, state
            self.initial_observation = state['observation']
            self.status = 'succeeded' if state['status'] == 'succeeded' else 'paused'
            self.error, self.history, self.pending = '', [], None
            self.memory = DiscoveredGraph()
            self.memory.observe(observation_from(state['observation']))
            self.initial_knowledge = self.memory.snapshot()
            return self.snapshot()

    async def step(self, background=False):
        if self.continuous and not background:
            raise RunnerError('Pause before stepping manually')
        async with self.lock:
            if self.continuous and not background:
                raise RunnerError('Pause before stepping manually')
            if not self.state or self.status not in ('paused', 'running'):
                raise RunnerError('Create or reset a run before stepping')
            try:
                if self.state['observation']['turn'] >= self.config['max_turns']:
                    await self.client.end(self.state['run_id'])
                    self.status = 'limit_reached'
                    self.state['status'] = 'stopped'
                    self.error = ''
                    return self.snapshot()
                if self.pending is None:
                    observation = observation_from(self.state['observation'])
                    decision = await asyncio.to_thread(self.policy.decide, observation, self.memory.view())
                    if not isinstance(decision.action, (Move, Stop)):
                        raise RunnerError('Policy must return Move or Stop')
                    # Serialize traces before applying a move: bad student telemetry
                    # must not leave an applied move missing from the history.
                    trace = trace_dict(decision.trace)
                    json.dumps({'trace': trace, 'explanation': decision.explanation}, allow_nan=False)
                    self.pending = (str(uuid4()), decision, trace)
                action_id, decision, trace = self.pending
                event = await self.client.apply(self.state['run_id'], self.state['observation']['turn'],
                                                action_id, decision.action)
                self.state['observation'] = event['observation']
                self.state['cumulative_cost'] = event['cumulative_cost']
                self.memory.observe(observation_from(event['observation']))
                self.history.append(dict(**event, explanation=decision.explanation,
                                         trace=trace, knowledge=self.memory.snapshot()))
                self.pending = None
                self.error = ''
                if event['observation']['goal_reached']:
                    self.status = self.state['status'] = 'succeeded'
                elif event['action'] == 'stop':
                    self.status = self.state['status'] = 'stopped'
                elif event['turn'] >= self.config['max_turns']:
                    await self.client.end(self.state['run_id'])
                    self.status = 'limit_reached'
                    self.state['status'] = 'stopped'
                else:
                    self.status = 'running' if self.continuous else 'paused'
                return self.snapshot()
            except Exception as exc:
                self.status = 'paused'
                self.continuous = False
                if isinstance(exc, grpc.aio.AioRpcError):
                    self.error = exc.details() or exc.code().name
                    if exc.code() not in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                        self.pending = None
                else:
                    self.error = f'{type(exc).__name__}: {exc}'
                    self.pending = None
                raise RunnerError(self.error) from exc

    async def run(self):
        async with self.lock:
            if not self.state or self.status != 'paused':
                raise RunnerError('Create a paused run before running')
            if self.task and not self.task.done():
                raise RunnerError('Execution is already active')
            self.continuous = True
            self.status = 'running'
            self.task = asyncio.create_task(self.loop())
            return self.snapshot()

    async def loop(self):
        try:
            while self.continuous and self.status == 'running':
                await self.step(background=True)
                if self.status != 'running':
                    break
                await asyncio.sleep(self.config['interval_ms'] / 1000)
        except RunnerError:
            pass
        finally:
            self.continuous = False

    async def pause(self):
        self.continuous = False
        if self.task:
            await self.task
        async with self.lock:
            if self.status == 'running':
                self.status = 'paused'
            return self.snapshot()

    async def stop(self):
        await self.pause()
        async with self.lock:
            if self.state:
                try:
                    self.state = await self.client.end(self.state['run_id'])
                except grpc.aio.AioRpcError as exc:
                    if exc.code() != grpc.StatusCode.NOT_FOUND:
                        raise
                    self.state['status'] = 'stopped'
                self.status = self.state['status']
                self.error = ''
            else:
                await self.end_environment_run()
            return self.snapshot()

    async def end_environment_run(self):
        try:
            state = self.state or await self.client.current()
            ended = await self.client.end(state['run_id'])
            if self.state:
                self.state = ended
                self.status = ended['status']
        except grpc.aio.AioRpcError as exc:
            if exc.code() != grpc.StatusCode.NOT_FOUND:
                raise
            if self.state:
                self.state['status'] = self.status = 'stopped'
