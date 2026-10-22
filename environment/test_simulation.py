"""Exercise the real HTTP + gRPC + agent loop, including retry semantics."""

import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import grpc
import httpx
from contracts import simulation_pb2 as pb
from environment.api import app as environment_app
from agent.api import app as agent_app
from agent.environment_client import EnvironmentClient, as_dict
from agent.models import Decision, Move
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

    async def test_local_observation_and_read_only_full_graph(self):
        await self.env.post('/grid/weights/0/1', json={'weight': 7})
        await self.env.post('/grid/obstacles/1/0')
        state = await self.create()
        observation = state['run']['observation']
        self.assertEqual(set(observation), {'run_id', 'turn', 'position', 'goal', 'current_cell_weight',
                                           'goal_distances', 'neighbors', 'goal_reached'})
        self.assertEqual(observation['neighbors'][0]['position'], {'x': 0, 'y': 1})
        self.assertEqual(len(observation['neighbors']), 2)
        self.assertEqual(observation['goal_distances'], {'l1': 4, 'l2': 8 ** .5, 'squared_l2': 8, 'mse': 4, 'linf': 2})
        self.assertEqual(len(state['knowledge']), 8)
        graph = agent_app.state.runner.memory.view()
        self.assertEqual(graph.edges[(0, 0)][(0, 1)], 7)
        self.assertEqual(graph.edges[(0, 1)][(0, 0)], 1)
        with self.assertRaises(TypeError):
            graph.edges[(0, 0)][(0, 1)] = 0

    async def test_full_knowledge_seeds_frozen_walkable_grid(self):
        await self.env.post('/grid/weights/0/1', json={'weight': 7})
        await self.env.post('/grid/obstacles/1/0')
        state = await self.create()
        cells = {(cell['x'], cell['y']): cell for cell in state['knowledge']}
        self.assertEqual(len(cells), 8)
        self.assertNotIn((1, 0), cells)
        self.assertEqual(cells[(0, 1)]['weight'], 7)
        self.assertEqual({node for node, cell in cells.items() if cell['visited']}, {(0, 0)})
        graph = agent_app.state.runner.memory.view()
        self.assertEqual(graph.edges[(0, 0)][(0, 1)], 7)
        self.assertEqual(graph.edges[(0, 1)][(0, 0)], 1)
        self.assertEqual(graph.edges[(0, 0)][(1, 1)], 1)
        self.assertEqual(graph.edges[(1, 2)][(2, 1)], 1)
        self.assertTrue(all(node not in edges for node, edges in graph.edges.items()))

    async def test_diagonal_move_between_obstacles_charges_destination_weight(self):
        await self.env.post('/grid/obstacles/0/1')
        await self.env.post('/grid/obstacles/1/0')
        await self.env.post('/grid/weights/1/1', json={'weight': 7})
        state = await self.client.start('diagonal')
        self.assertEqual([n['position'] for n in state['observation']['neighbors']],
                         [{'x': 1, 'y': 1}])
        event = await self.client.apply(state['run_id'], 0, 'diagonal-move', Move((1, 1)))
        self.assertEqual(event['to'], {'x': 1, 'y': 1})
        self.assertEqual(event['step_cost'], 7)
        self.assertEqual(event['cumulative_cost'], 7)

    async def test_astar_can_switch_away_from_zero_on_reset(self):
        state = await self.create(heuristic='zero')
        self.assertEqual(state['config']['heuristic'], 'zero')
        self.assertEqual(agent_app.state.runner.policy.config.heuristic, 'zero')
        state = await self.create(heuristic='l1')
        self.assertEqual(state['config']['heuristic'], 'l1')
        self.assertEqual(agent_app.state.runner.policy.config.heuristic, 'l1')
        self.assertIsNone(agent_app.state.runner.policy.path)

    async def test_weighted_detour_is_searched_once_and_reused(self):
        await self.configure((0, 0), (2, 0))
        await self.env.post('/grid/weights/1/0', json={'weight': 9})
        for algorithm, heuristic in (('dijkstra', 'squared_l2'), ('astar', 'zero'), ('astar', 'linf')):
            with self.subTest(algorithm=algorithm, heuristic=heuristic):
                await self.create(algorithm=algorithm, heuristic=heuristic)
                policy = agent_app.state.runner.policy
                with patch.object(policy.algorithm, 'search', wraps=policy.algorithm.search) as search:
                    for _ in range(3):
                        response = await self.agent.post('/step')
                        self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(search.call_count, 1)
                state = response.json()
                self.assertEqual(state['status'], 'succeeded')
                self.assertEqual(state['run']['cumulative_cost'], 2)
                self.assertEqual(state['final_path'], [
                    {'x': 0, 'y': 0}, {'x': 1, 'y': 1}, {'x': 2, 'y': 0}])
                history = (await self.agent.get('/history')).json()['events']
                self.assertTrue(history[0]['trace']['expanded'])
                self.assertTrue(history[0]['trace']['scores'])
                scores = history[0]['trace']['scores']
                if algorithm == 'dijkstra' or heuristic == 'zero':
                    self.assertTrue(all(score['h'] == 0 and score['f'] == score['g'] for score in scores))
                else:
                    start_score = next(score for score in scores if (score['x'], score['y']) == (0, 0))
                    self.assertEqual(start_score['h'], 2)
                self.assertFalse(history[1]['trace']['expanded'])
                self.assertEqual(len(history[0]['knowledge']), len(history[1]['knowledge']))

    async def test_algorithm_selection_and_invalid_configuration(self):
        algorithms = (await self.agent.get('/algorithms')).json()
        self.assertEqual({item['id'] for item in algorithms}, {'dijkstra', 'astar', 'weighted_astar'})
        for body in ({'algorithm': 'explorer'}, {'heuristic': 'unknown'}):
            response = await self.agent.post('/runs', json=body)
            self.assertEqual(response.status_code, 422)
        for algorithm in ('dijkstra', 'astar', 'weighted_astar'):
            with self.subTest(algorithm=algorithm):
                state = await self.create(algorithm=algorithm, heuristic='linf')
                self.assertEqual(state['config']['algorithm'], algorithm)
                self.assertEqual(len(state['knowledge']), 9)
                for _ in range(3):
                    response = await self.agent.post('/step')
                    self.assertEqual(response.status_code, 200, response.text)
                state = response.json()
                self.assertEqual(state['status'], 'succeeded')
                self.assertEqual(sum(cell['visited'] for cell in state['knowledge']), 3)
                self.assertEqual(state['run']['cumulative_cost'], 2)

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

    async def test_agent_reaches_goal_and_history_reconstructs_movement(self):
        await self.env.post('/grid/obstacles/1/0')
        await self.env.post('/grid/weights/0/1', json={'weight': 6})
        await self.create()
        for _ in range(20):
            result = await self.agent.post('/step')
            self.assertEqual(result.status_code, 200, result.text)
            if result.json()['status'] == 'succeeded':
                break
        else:
            self.fail('Agent did not reach the goal')
        state = result.json()
        history = (await self.agent.get('/history')).json()['events']
        position = {'x': 0, 'y': 0}
        cost = 0
        for event in history:
            self.assertEqual(event['from'], position)
            position = event['to']
            distance = max(abs(event['from']['x'] - position['x']), abs(event['from']['y'] - position['y']))
            self.assertEqual(distance, 1 if event['action'] == 'move' else 0)
            cost += event['step_cost']
            self.assertEqual(cost, event['cumulative_cost'])
            self.assertEqual(event['observation']['position'], position)
            if event['action'] == 'move':
                self.assertTrue(event['trace']['candidate_path'])
        self.assertEqual(position, {'x': 2, 'y': 2})
        self.assertFalse(all(cell['visited'] for cell in state['knowledge']))
        self.assertEqual([event['to'] for event in history if event['action'] == 'move'],
                         [{'x': 1, 'y': 1}, {'x': 2, 'y': 2}])
        self.assertEqual(cost, 2)
        self.assertEqual(state['run']['cumulative_cost'], cost)
        self.assertEqual(state['final_path'][0], {'x': 0, 'y': 0})
        self.assertEqual(state['final_path'][-1], {'x': 2, 'y': 2})
        for origin, target in zip(state['final_path'], state['final_path'][1:]):
            self.assertEqual(max(abs(origin['x'] - target['x']), abs(origin['y'] - target['y'])), 1)
        self.assertEqual((await self.env.get('/scenario')).json()['locked'], False)
        await self.create()
        self.assertEqual((await self.agent.get('/history')).json()['events'], [])
        self.assertEqual(len((await self.agent.get('/state')).json()['knowledge']), 8)

    async def test_unreachable_goal_limits_and_start_at_goal(self):
        await self.env.post('/grid/obstacles/stroke', json={
            'obstacle': True, 'cells': [{'x': 0, 'y': 1}, {'x': 1, 'y': 0}, {'x': 1, 'y': 1}]})
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
        self.assertEqual(state['status'], 'paused')
        self.assertEqual(state['run']['observation']['turn'], 0)
        self.assertEqual(state['run']['cumulative_cost'], 0)

    async def test_agent_stops_at_goal_without_exploring_remaining_cells(self):
        await self.configure((0, 0), (1, 0))
        await self.env.post('/grid/obstacles/stroke', json={
            'obstacle': True,
            'cells': [{'x': x, 'y': y} for y in (1, 2) for x in range(3)],
        })
        await self.create()
        first_goal_visit = (await self.agent.post('/step')).json()
        self.assertEqual(first_goal_visit['status'], 'paused')
        self.assertTrue(first_goal_visit['run']['observation']['goal_reached'])
        self.assertTrue((await self.env.get('/scenario')).json()['locked'])
        state = (await self.agent.post('/step')).json()
        self.assertEqual(state['status'], 'succeeded')
        self.assertEqual(state['run']['observation']['position'], {'x': 1, 'y': 0})
        self.assertEqual({(cell['x'], cell['y']) for cell in state['knowledge'] if cell['visited']},
                         {(0, 0), (1, 0)})
        history = (await self.agent.get('/history')).json()['events']
        self.assertEqual([event['action'] for event in history], ['move', 'stop'])
        self.assertFalse((await self.env.get('/scenario')).json()['locked'])

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

    async def test_start_at_goal_stops_without_moving(self):
        await self.configure((0, 0), (0, 0))
        await self.create(heuristic='linf')
        state = (await self.agent.post('/step')).json()
        self.assertEqual(state['status'], 'succeeded')
        self.assertEqual(state['run']['cumulative_cost'], 0)
        self.assertEqual(state['final_path'], [{'x': 0, 'y': 0}])
        self.assertEqual(sum(cell['visited'] for cell in state['knowledge']), 1)
        history = (await self.agent.get('/history')).json()['events']
        self.assertEqual([event['action'] for event in history], ['stop'])

    async def test_agent_ignores_disconnected_cells(self):
        await self.configure((0, 0), (0, 2))
        await self.env.post('/grid/obstacles/stroke', json={
            'obstacle': True, 'cells': [{'x': 1, 'y': y} for y in range(3)]})
        await self.create()
        for _ in range(10):
            response = await self.agent.post('/step')
            self.assertEqual(response.status_code, 200, response.text)
            state = response.json()
            if state['status'] == 'succeeded':
                break
        else:
            self.fail('Disconnected known cells prevented completion')
        self.assertEqual({(cell['x'], cell['y']) for cell in state['knowledge'] if cell['visited']},
                         {(0, 0), (0, 1), (0, 2)})
        self.assertEqual(len(state['knowledge']), 6)

    async def test_invalid_student_action_pauses_without_moving(self):
        class BrokenPolicy:
            def reset(self, config): pass
            def decide(self, observation, knowledge): return Decision(Move((20, 20)))
        with patch('agent.runner.Agent', BrokenPolicy):
            await self.create()
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
        with patch('agent.runner.Agent', BrokenInitialization):
            response = await self.agent.post('/runs', json={})
            self.assertEqual(response.status_code, 409)
            self.assertIn('Initialize student state', response.json()['detail'])
        state = (await self.agent.post('/step')).json()
        self.assertEqual(state['run']['run_id'], original['run']['run_id'])
        self.assertEqual(state['run']['observation']['turn'], 1)
