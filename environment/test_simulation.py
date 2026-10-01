"""Exercise the real HTTP + gRPC + agent loop, including retry semantics."""

import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import grpc
import httpx
from contracts import simulation_pb2 as pb
from environment.api import app as environment_app
from agent.api import app as agent_app
from agent.environment_client import EnvironmentClient, as_dict, observation_from
from agent.memory import DiscoveredGraph
from agent.models import Decision, Move
from agent.registry import ALGORITHMS, Algorithm
from agent.runner import Runner


class SimulationIntegrationTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env_vars = patch.dict('os.environ', {'GRPC_PORT': '0', 'GRPC_HOST': '127.0.0.1'})
        self.env_vars.start()
        self.addCleanup(self.env_vars.stop)
        await self.enterAsyncContext(environment_app.router.lifespan_context(environment_app))
        self.env = await self.enterAsyncContext(httpx.AsyncClient(
            transport=httpx.ASGITransport(app=environment_app), base_url='http://environment'))
        self.address = f'127.0.0.1:{environment_app.state.grpc_port}'
        self.agent_vars = patch.dict('os.environ', {'ENVIRONMENT_GRPC_ADDRESS': self.address})
        self.agent_vars.start()
        self.addCleanup(self.agent_vars.stop)
        await self.enterAsyncContext(agent_app.router.lifespan_context(agent_app))
        self.agent = await self.enterAsyncContext(httpx.AsyncClient(
            transport=httpx.ASGITransport(app=agent_app), base_url='http://agent'))
        self.client = EnvironmentClient(self.address)
        self.addAsyncCleanup(self.client.close)
        await self.env.post('/grid/resize', json={'size': 3})
        await self.configure((0, 0), (2, 2))

    async def configure(self, start, goal):
        result = await self.env.post('/scenario', json={
            'start': dict(zip(('x', 'y'), start)), 'goal': dict(zip(('x', 'y'), goal))})
        self.assertEqual(result.status_code, 200, result.text)

    async def create(self, **changes):
        result = await self.agent.post('/runs', json={'interval_ms': 50, **changes})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    async def test_local_observation_and_directional_memory(self):
        await self.env.post('/grid/weights/0/1', json={'weight': 7})
        await self.env.post('/grid/obstacles/1/0')
        state = await self.create()
        observation = state['run']['observation']
        self.assertEqual(set(observation), {'run_id', 'turn', 'position', 'goal', 'current_cell_weight',
                                           'goal_distances', 'neighbors', 'goal_reached'})
        self.assertEqual(observation['neighbors'][0]['position'], {'x': 0, 'y': 1})
        self.assertEqual(len(observation['neighbors']), 1)
        self.assertEqual(observation['goal_distances'], {'l1': 4, 'l2': 8 ** .5, 'squared_l2': 8, 'mse': 4, 'linf': 2})
        self.assertEqual({(c['x'], c['y']) for c in state['knowledge']}, {(0, 0), (0, 1)})
        graph = DiscoveredGraph()
        graph.observe(observation_from(observation))
        self.assertEqual(graph.view().edges[(0, 0)][(0, 1)], 7)
        self.assertEqual(graph.view().edges[(0, 1)][(0, 0)], 1)
        with self.assertRaises(TypeError):
            graph.view().edges[(0, 0)][(0, 1)] = 0

    async def test_idempotency_stale_turns_and_invalid_moves(self):
        state = await self.client.start('start-once')
        self.assertEqual(await self.client.start('start-once'), state)
        run_id = state['run_id']
        with self.assertRaises(grpc.aio.AioRpcError) as error:
            await self.client.apply(run_id, 0, 'invalid', Move((2, 2)))
        self.assertEqual(error.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)
        first = await self.client.apply(run_id, 0, 'move-once', Move((0, 1)))
        second = await self.client.apply(run_id, 1, 'back', Move((0, 0)))
        self.assertEqual(second['cumulative_cost'], 2)
        self.assertEqual(await self.client.apply(run_id, 0, 'move-once', Move((0, 1))), first)
        for turn, action_id, target in ((0, 'stale', (1, 0)), (0, 'move-once', (1, 0))):
            with self.assertRaises(grpc.aio.AioRpcError):
                await self.client.apply(run_id, turn, action_id, Move(target))
        events = as_dict(await self.client.stub.GetTurnEvents(pb.EventsRequest(run_id=run_id, after_sequence=1)))
        self.assertEqual([e['turn'] for e in events['events']], [2])
        self.assertEqual((await self.client.current())['observation']['turn'], 2)
        await self.client.end(run_id)

    async def test_scenario_validation_endpoint_protection_and_run_lock(self):
        await self.env.post('/grid/obstacles/1/1')
        before = (await self.env.get('/grid/render')).json()
        result = await self.env.post('/grid/obstacles/stroke', json={
            'obstacle': True, 'cells': [{'x': 1, 'y': 0}, {'x': 0, 'y': 0}]})
        self.assertEqual(result.status_code, 409)
        self.assertEqual((await self.env.get('/grid/render')).json(), before)
        for start in ({'x': 1, 'y': 1}, {'x': -1, 'y': 0}, {'x': True, 'y': 0}):
            response = await self.env.post('/scenario', json={'start': start, 'goal': {'x': 2, 'y': 2}})
            self.assertEqual(response.status_code, 422)
        await self.create()
        for route, body in (('/grid/reset', {}), ('/grid/resize', {'size': 4}),
                            ('/grid/weights', {'weight': 9}), ('/grid/obstacles/1/0', {}),
                            ('/scenario', {'start': None, 'goal': None})):
            self.assertEqual((await self.env.post(route, json=body)).status_code, 409)
        await self.agent.post('/stop')
        run_id = (await self.agent.get('/state')).json()['run']['run_id']
        self.assertEqual((await self.env.post('/grid/resize', json={'size': 4})).status_code, 200)
        replay_grid = (await self.env.get(f'/runs/{run_id}/grid')).json()
        self.assertEqual(replay_grid['width'], 3)
        self.assertEqual(replay_grid['cells'][1][1], 'obstacle')
        self.assertIsNone((await self.env.get('/scenario')).json()['goal'])
        self.assertEqual((await self.agent.post('/runs', json={})).status_code, 409)
        # Completed run state survives edits that invalidate its original cells.
        self.assertEqual((await self.client.current())['observation']['position'], {'x': 0, 'y': 0})

    async def test_example_reaches_goal_and_history_reconstructs_movement(self):
        await self.env.post('/grid/obstacles/1/0')
        await self.env.post('/grid/weights/0/1', json={'weight': 6})
        await self.create()
        for _ in range(20):
            result = await self.agent.post('/step')
            self.assertEqual(result.status_code, 200, result.text)
            if result.json()['status'] == 'succeeded':
                break
        else:
            self.fail('Example explorer did not reach the goal')
        state = result.json()
        history = (await self.agent.get('/history')).json()['events']
        position = {'x': 0, 'y': 0}
        cost = 0
        for event in history:
            self.assertEqual(event['from'], position)
            position = event['to']
            self.assertEqual(abs(event['from']['x'] - position['x']) + abs(event['from']['y'] - position['y']), 1)
            cost += event['step_cost']
            self.assertEqual(cost, event['cumulative_cost'])
            self.assertEqual(event['observation']['position'], position)
            self.assertTrue(event['trace']['candidate_path'])
        self.assertEqual(position, {'x': 2, 'y': 2})
        self.assertEqual(state['run']['cumulative_cost'], cost)
        self.assertEqual((await self.env.get('/scenario')).json()['locked'], False)
        await self.create()
        self.assertEqual((await self.agent.get('/history')).json()['events'], [])
        self.assertEqual(len((await self.agent.get('/state')).json()['knowledge']), 2)

    async def test_unreachable_goal_limits_and_start_at_goal(self):
        await self.env.post('/grid/obstacles/stroke', json={
            'obstacle': True, 'cells': [{'x': 0, 'y': 1}, {'x': 1, 'y': 0}]})
        await self.create()
        state = (await self.agent.post('/step')).json()
        self.assertEqual(state['status'], 'stopped')
        history = (await self.agent.get('/history')).json()['events']
        self.assertEqual(history[0]['action'], 'stop')
        self.assertEqual(history[0]['step_cost'], 0)
        await self.env.post('/grid/reset')
        await self.create(max_turns=1)
        state = (await self.agent.post('/step')).json()
        self.assertEqual(state['status'], 'limit_reached')
        self.assertEqual((await self.agent.post('/step')).status_code, 409)
        self.assertFalse((await self.env.get('/scenario')).json()['locked'])
        await self.configure((0, 0), (0, 0))
        state = await self.create()
        self.assertEqual(state['status'], 'succeeded')
        self.assertEqual(state['run']['observation']['turn'], 0)
        self.assertEqual(state['run']['cumulative_cost'], 0)

    async def test_run_pause_and_resume(self):
        await self.create(interval_ms=100)
        self.assertEqual((await self.agent.post('/run')).status_code, 200)
        await asyncio.sleep(.03)
        self.assertEqual((await self.agent.post('/step')).status_code, 409)
        state = (await self.agent.post('/pause')).json()
        self.assertEqual(state['status'], 'paused')
        turn = state['run']['observation']['turn']
        self.assertGreaterEqual(turn, 1)
        await asyncio.sleep(.15)
        self.assertEqual((await self.agent.get('/state')).json()['run']['observation']['turn'], turn)
        state = (await self.agent.post('/step')).json()
        self.assertEqual(state['run']['observation']['turn'], turn + 1)

    async def test_invalid_student_action_pauses_without_moving(self):
        class BrokenPolicy:
            def reset(self, config): pass
            def decide(self, observation, knowledge): return Decision(Move((20, 20)))
        with patch.dict(ALGORITHMS, {'broken': Algorithm('Broken', 'Test policy', lambda _: BrokenPolicy())}):
            await self.create(algorithm='broken')
            result = await self.agent.post('/step')
            self.assertEqual(result.status_code, 409)
            state = (await self.agent.get('/state')).json()
            self.assertEqual(state['status'], 'paused')
            self.assertEqual(state['run']['observation']['turn'], 0)
            self.assertEqual(state['history_count'], 0)
            self.assertIn('neighbor', state['error'])

    async def test_committed_move_timeout_recovers_without_second_decision(self):
        runner = agent_app.state.runner
        await self.create()
        apply = runner.client.apply
        first = True
        async def timeout_after_commit(*args):
            nonlocal first
            event = await apply(*args)
            if first:
                first = False
                raise grpc.aio.AioRpcError(grpc.StatusCode.DEADLINE_EXCEEDED, (), (), 'Reply lost')
            return event
        with patch.object(runner.client, 'apply', timeout_after_commit):
            self.assertEqual((await self.agent.post('/step')).status_code, 409)
            self.assertIsNotNone(runner.pending)
            self.assertEqual((await self.client.current())['observation']['turn'], 1)
            recovered = (await self.agent.post('/step')).json()
            self.assertEqual(recovered['run']['observation']['turn'], 1)
            self.assertEqual(recovered['history_count'], 1)
            self.assertIsNone(runner.pending)

    async def test_fresh_agent_can_release_orphan_run(self):
        await self.create()
        fresh = Runner(self.client)
        await fresh.stop()
        self.assertFalse((await self.env.get('/scenario')).json()['locked'])

    async def test_failed_student_initialization_preserves_existing_run(self):
        class BrokenInitialization:
            def reset(self, config):
                raise NotImplementedError('Initialize student state')
        original = await self.create()
        with patch.dict(ALGORITHMS, {'broken': Algorithm('Broken', 'Test initialization', lambda _: BrokenInitialization())}):
            response = await self.agent.post('/runs', json={'algorithm': 'broken'})
            self.assertEqual(response.status_code, 409)
            self.assertIn('Initialize student state', response.json()['detail'])
        state = (await self.agent.post('/step')).json()
        self.assertEqual(state['run']['run_id'], original['run']['run_id'])
        self.assertEqual(state['run']['observation']['turn'], 1)
