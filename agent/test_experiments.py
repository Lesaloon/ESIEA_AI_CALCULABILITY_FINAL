"""Greedy, simulated annealing, tabu search and the control-panel experiments."""

from unittest import TestCase

from fastapi.testclient import TestClient

from agent.algorithms.astar import AStar
from agent.algorithms.dijkstra import Dijkstra
from agent.algorithms.greedy import Greedy
from agent.algorithms.optimizers import SimulatedAnnealing, TabuSearch, path_cost
from agent.api import app
from agent.experiments import MapConfig, admissible, benchmark, build_map, obstacle_cells, transfer, tune
from agent.test_optimizers import open_grid


class GreedyTests(TestCase):
    def test_greedy_goes_straight_on_an_open_map(self):
        graph = open_grid(10)
        result = Greedy('linf').search(graph, (0, 0), (9, 9))
        self.assertEqual(len(result.path), 10)                  # nine diagonal moves
        self.assertLess(len(result.trace.expanded), len(AStar('linf').search(graph, (0, 0), (9, 9)).trace.expanded) + 1)

    def test_greedy_is_not_optimal_in_the_u_trap(self):
        graph, start, goal, _ = build_map(MapConfig(20, 4, 'u', 'random'))
        greedy = Greedy('l1').search(graph, start, goal)
        optimal = path_cost(graph, Dijkstra().search(graph, start, goal).path)
        self.assertGreater(path_cost(graph, greedy.path), optimal)


class LocalSearchTests(TestCase):
    def setUp(self):
        self.graph = open_grid(10, {(x, y): 1 + (x * 3 + y * 5) % 7 for x in range(10) for y in range(10)})

    def tune(self, optimizer, **values):
        values.setdefault('time_weight', 0)   # time is noisy: keep runs comparable
        return optimizer(values).tune(self.graph, (0, 0), (9, 9), 'l1', 2.0)

    def test_annealing_is_reproducible_bounded_and_keeps_its_best_point(self):
        first = self.tune(SimulatedAnnealing, weight_min=1, weight_max=3, step=0.5, max_iterations=25, seed=3)
        second = self.tune(SimulatedAnnealing, weight_min=1, weight_max=3, step=0.5, max_iterations=25, seed=3)
        self.assertEqual(first[:2], second[:2])
        trials = first[2]
        self.assertTrue(all(1 <= t['weight'] <= 3 for t in trials))
        best = min(t['score'] for t in trials if t['score'] is not None)
        chosen = next(t for t in trials if (t['heuristic'], t['weight']) == first[:2])
        self.assertEqual(chosen['score'], best)

    def test_zero_temperature_behaves_like_hill_climbing(self):
        heuristic, weight, trials, _ = self.tune(SimulatedAnnealing, temperature=0, max_iterations=30)
        scores = {(t['heuristic'], t['weight']): t['score'] for t in trials}
        self.assertLessEqual(scores[(heuristic, weight)], scores[('l1', 2.0)])

    def test_tabu_never_tests_a_point_twice_and_keeps_moving(self):
        heuristic, weight, trials, _ = self.tune(TabuSearch, lock_heuristic=1, weight_min=1, weight_max=5,
                                                 step=0.5, max_iterations=6)
        weights = [t['weight'] for t in trials]
        self.assertEqual(len(weights), len(set(weights)))
        self.assertGreaterEqual(len(weights), 7)      # the start plus one new point per move
        self.assertEqual(heuristic, 'l1')
        best = min(t['score'] for t in trials)
        self.assertEqual(next(t['score'] for t in trials if t['weight'] == weight), best)

    def test_parameter_validation(self):
        for optimizer in (SimulatedAnnealing, TabuSearch):
            with self.subTest(optimizer=optimizer.__name__):
                with self.assertRaises(ValueError):
                    optimizer.resolve({'weight_min': 4, 'weight_max': 2})
        with self.assertRaises(ValueError):
            SimulatedAnnealing.resolve({'temperature': 2})


class MapTests(TestCase):
    def test_maps_are_reproducible_and_reachable(self):
        for obstacle in ('none', 'u', 'wall', 'random'):
            for connectivity in (4, 8):
                with self.subTest(obstacle=obstacle, connectivity=connectivity):
                    config = MapConfig(12, connectivity, obstacle, 'random', 5)
                    first, second = build_map(config), build_map(config)
                    self.assertEqual(first[3], second[3])
                    graph, start, goal, _ = first
                    self.assertTrue(Dijkstra().search(graph, start, goal).path)

    def test_connectivity_sets_the_number_of_neighbors(self):
        four, _, _, _ = build_map(MapConfig(10, 4, 'none'))
        eight, _, _, _ = build_map(MapConfig(10, 8, 'none'))
        self.assertEqual((len(four.edges[(0, 0)]), len(four.edges[(5, 5)])), (2, 4))
        self.assertEqual((len(eight.edges[(0, 0)]), len(eight.edges[(5, 5)])), (3, 8))

    def test_u_opens_toward_the_start_and_wall_keeps_a_passage(self):
        u = obstacle_cells('u', 20)
        self.assertIn((11, 10), u)          # bottom of the cup, on the start-goal row
        self.assertNotIn((7, 10), u)        # its opening faces the start
        wall = obstacle_cells('wall', 20)
        self.assertEqual({y for _, y in wall}, set(range(18)))

    def test_admissibility_depends_on_connectivity(self):
        self.assertTrue(admissible('l1', 4) and admissible('l2', 4) and admissible('linf', 8))
        self.assertFalse(admissible('l1', 8) or admissible('l2', 8) or admissible('squared_l2', 4))


class ExperimentTests(TestCase):
    def test_benchmark_compares_against_dijkstra(self):
        result = benchmark(sizes=[12], connectivities=[4, 8], heuristics=['l1', 'linf'], obstacles=['u'], repeat=1)
        self.assertEqual(len(result['rows']), 2 * (1 + 3 * 2))
        for row in result['rows']:
            self.assertGreaterEqual(row['cost_ratio'], 1 - 1e-9)
            if row['algorithm'] in ('dijkstra', 'astar') and row['admissible']:
                self.assertTrue(row['optimal'], row)
        dijkstra = next(r for r in result['rows'] if r['algorithm'] == 'dijkstra')
        self.assertEqual(dijkstra['expanded_vs_dijkstra'], 1)

    def test_transfer_compares_four_strategies(self):
        result = transfer(heuristic='linf', weight=2, sizes=[10], connectivities=[8], obstacles=['none', 'u'],
                          weight_max=3, weight_step=1, time_weight=0)
        self.assertEqual(len(result['rows']), 2)
        for row in result['rows']:
            # Re-optimizing on each map is the best possible point of the grid.
            self.assertLessEqual(row['retuned']['score'], row['fixed']['score'] + 1e-9)
            self.assertLessEqual(row['retuned']['score'], row['robust']['score'] + 1e-9)
            self.assertGreaterEqual(row['fixed']['regret'], -1e-9)
        self.assertIn(result['summary']['robust']['weight'], (1, 2, 3))

    def test_too_large_requests_are_refused(self):
        with self.assertRaises(ValueError):
            transfer(sizes=[40, 40, 40, 40], obstacles=['none', 'u', 'wall', 'random'], weight_step=0.1,
                     weight_max=20)


class TuneTests(TestCase):
    def test_methods_share_the_same_scores_and_the_grid_finds_the_landscape_minimum(self):
        params = dict(weight_min=1, weight_max=3, weight_step=0.5, step=0.5, time_weight=0)
        result = tune(size=12, connectivity=8, obstacle='u', params=params)
        self.assertEqual({m['id'] for m in result['methods']},
                         {'grid', 'random', 'hill_climbing', 'simulated_annealing', 'tabu'})
        landscape_best = min(p['score'] for curve in result['landscape'] for p in curve['points']
                             if p['score'] is not None and (p['weight'] * 2).is_integer())
        grid = next(m for m in result['methods'] if m['id'] == 'grid')
        self.assertAlmostEqual(grid['score'], landscape_best)
        for method in result['methods']:
            self.assertGreaterEqual(method['score'], landscape_best - 1e-9)
            self.assertGreaterEqual(method['cost_ratio'], 1 - 1e-9)
            self.assertEqual(method['evaluations'], len(method['visited']))

    def test_locked_heuristic_draws_a_single_curve(self):
        result = tune(size=10, optimizers=['hill_climbing'], heuristic='linf',
                      params=dict(lock_heuristic=1, weight_max=2))
        self.assertEqual([c['heuristic'] for c in result['landscape']], ['linf'])
        self.assertEqual(result['methods'][0]['heuristic'], 'linf')


class ApiTests(TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_benchmark_endpoint(self):
        response = self.client.post('/experiments/benchmark', json=dict(
            sizes=[10], connectivities=[8], obstacles=['wall'], heuristics=['linf'], repeat=1))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['rows']), 4)

    def test_transfer_endpoint_and_validation(self):
        response = self.client.post('/experiments/transfer', json=dict(
            sizes=[10], connectivities=[4], obstacles=['none'], weight_max=2, weight_step=1))
        self.assertEqual(response.status_code, 200, response.text)
        for body in (dict(sizes=[50]), dict(weight_min=4, weight_max=2), dict(heuristics=['bogus']),
                     dict(cost_weight=0, time_weight=0, memory_weight=0)):
            with self.subTest(body=body):
                url = '/experiments/benchmark' if 'heuristics' in body else '/experiments/transfer'
                self.assertEqual(self.client.post(url, json=body).status_code, 422)

    def test_tune_endpoint_and_validation(self):
        response = self.client.post('/experiments/tune', json=dict(size=10, optimizers=['grid', 'tabu'],
                                                                   params=dict(weight_max=2, weight_step=1)))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['methods']), 2)
        # The panel always sends every setting, including those of unselected methods.
        response = self.client.post('/experiments/tune', json=dict(size=10, optimizers=['tabu'],
                                                                   params=dict(weight_max=2, weight_step=1, trials=5)))
        self.assertEqual(response.status_code, 200, response.text)
        for body in (dict(params=dict(weight_min=4, weight_max=2)), dict(params=dict(bogus=1)),
                     dict(optimizers=['nope']), dict(size=60)):
            with self.subTest(body=body):
                self.assertEqual(self.client.post('/experiments/tune', json=body).status_code, 422)

    def test_new_optimizers_and_algorithm_are_listed(self):
        ids = {o['id'] for o in self.client.get('/optimizers').json()}
        self.assertTrue({'simulated_annealing', 'tabu'} <= ids)
        self.assertIn('greedy', {a['id'] for a in self.client.get('/algorithms').json()})
