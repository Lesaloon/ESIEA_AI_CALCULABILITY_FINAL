"""Weighted A* and parameter optimizers, without any transport."""

from unittest import TestCase

from agent.algorithms.astar import AStar
from agent.algorithms.optimizers import GridSearch, HillClimbing, HEURISTICS, RandomSearch, path_cost
from agent.memory import RunGraph


def open_grid(size, weights=None):
    cells = [dict(position=dict(x=x, y=y), weight=(weights or {}).get((x, y), 1))
             for x in range(size) for y in range(size)]
    graph = RunGraph()
    graph.seed(dict(walkable_cells=cells))
    return graph.view()


class WeightedAStarTests(TestCase):
    def test_weight_one_is_classic_astar_and_larger_weight_expands_less(self):
        graph = open_grid(10, {(x, 5): 9 for x in range(1, 9)})
        classic = AStar('linf', 1.0).search(graph, (0, 0), (9, 9))
        greedy = AStar('linf', 5.0).search(graph, (0, 0), (9, 9))
        self.assertLessEqual(len(greedy.trace.expanded), len(classic.trace.expanded))
        self.assertLessEqual(path_cost(graph, classic.path), path_cost(graph, greedy.path))

    def test_cost_is_within_weight_times_optimum_for_admissible_heuristic(self):
        graph = open_grid(8, {(x, y): 1 + (x * 3 + y * 5) % 7 for x in range(8) for y in range(8)})
        optimum = path_cost(graph, AStar('linf', 1.0).search(graph, (0, 0), (7, 7)).path)
        for weight in (1.5, 2, 4):
            path = AStar('linf', weight).search(graph, (0, 0), (7, 7)).path
            self.assertLessEqual(path_cost(graph, path), weight * optimum)


class OptimizerTests(TestCase):
    def setUp(self):
        self.graph = open_grid(10, {(x, y): 1 + (x * 3 + y * 5) % 7 for x in range(10) for y in range(10)})

    def tune(self, optimizer, **values):
        # Time is noisy, so tests that compare runs ignore it.
        values.setdefault('time_weight', 0)
        heuristic, weight, trials, _ = optimizer(values).tune(self.graph, (0, 0), (9, 9), 'l1', 1.0)
        return heuristic, weight, trials

    def test_grid_search_tries_every_combination(self):
        heuristic, weight, trials = self.tune(GridSearch, weight_min=1, weight_max=2, weight_step=0.5)
        self.assertEqual(len(trials), len(HEURISTICS) * 3)
        self.assertEqual(min(t['score'] for t in trials), next(
            t['score'] for t in trials if (t['heuristic'], t['weight']) == (heuristic, weight)))

    def test_cost_only_prefers_the_cheapest_route(self):
        values = dict(memory_weight=0, weight_min=1, weight_max=3, weight_step=1)
        heuristic, weight, trials = self.tune(GridSearch, **values)
        chosen = next(t for t in trials if (t['heuristic'], t['weight']) == (heuristic, weight))
        self.assertEqual(chosen['cost'], min(t['cost'] for t in trials))

    def test_memory_only_prefers_the_leanest_search(self):
        values = dict(cost_weight=0, memory_weight=1, weight_min=1, weight_max=3, weight_step=1)
        heuristic, weight, trials = self.tune(GridSearch, **values)
        chosen = next(t for t in trials if (t['heuristic'], t['weight']) == (heuristic, weight))
        self.assertEqual(chosen['memory_kb'], min(t['memory_kb'] for t in trials))

    def test_trials_report_time_and_memory_against_a_reference(self):
        _, _, trials, reference = GridSearch(dict(weight_max=1)).tune(self.graph, (0, 0), (9, 9), 'l1', 1.0)
        self.assertEqual((reference['heuristic'], reference['weight']), ('linf', 1.0))
        self.assertTrue(all(t['time_ms'] > 0 and t['memory_kb'] > 0 and t['expanded'] > 0 for t in trials))
        linf = next(t for t in trials if t['heuristic'] == 'linf')
        self.assertEqual(linf['cost'], reference['cost'])

    def test_random_search_is_reproducible_and_bounded(self):
        first = self.tune(RandomSearch, trials=15, seed=7)
        second = self.tune(RandomSearch, trials=15, seed=7)
        self.assertEqual(first[:2], second[:2])
        self.assertEqual([(t["heuristic"], t["weight"]) for t in first[2]],
                         [(t["heuristic"], t["weight"]) for t in second[2]])
        self.assertLessEqual(len(first[2]), 15)
        self.assertTrue(all(1 <= t['weight'] <= 5 for t in first[2]))

    def test_random_search_stays_within_the_weight_range(self):
        _, _, trials = self.tune(RandomSearch, trials=40, weight_min=3, weight_max=3.4)
        self.assertTrue(all(3 <= t['weight'] <= 3.4 for t in trials))
        self.assertGreater(len({t['weight'] for t in trials}), 1)

    def test_hill_climbing_stays_within_the_weight_range(self):
        # The starting weight (1.0) is below the range, so it is clamped to weight_min.
        _, weight, trials = self.tune(HillClimbing, weight_min=2, weight_max=3, step=0.5, max_iterations=10)
        self.assertEqual(trials[0]['weight'], 2)
        self.assertTrue(all(2 <= t['weight'] <= 3 for t in trials))
        self.assertTrue(2 <= weight <= 3)

    def test_hill_climbing_never_ends_worse_than_its_start(self):
        heuristic, weight, trials = self.tune(HillClimbing, step=0.5, max_iterations=10)
        scores = {(t['heuristic'], t['weight']): t['score'] for t in trials}
        self.assertLessEqual(scores[(heuristic, weight)], scores[('l1', 1.0)])
        self.assertEqual(trials[0]['heuristic'], 'l1')

    def test_locked_heuristic_only_tunes_the_weight(self):
        for optimizer, values in ((GridSearch, dict(weight_min=1, weight_max=2, weight_step=0.5)),
                                  (RandomSearch, dict(trials=10)), (HillClimbing, dict(max_iterations=5))):
            with self.subTest(optimizer=optimizer.__name__):
                heuristic, _, trials = self.tune(optimizer, lock_heuristic=1, **values)
                self.assertEqual(heuristic, 'l1')
                self.assertEqual({t['heuristic'] for t in trials}, {'l1'})

    def test_locked_heuristic_is_kept_even_when_it_is_not_tunable(self):
        heuristic, _, trials, _ = GridSearch(dict(lock_heuristic=1, weight_max=1)).tune(
            self.graph, (0, 0), (9, 9), 'zero', 1.0)
        self.assertEqual((heuristic, {t['heuristic'] for t in trials}), ('zero', {'zero'}))

    def test_unreachable_goal_yields_null_scores(self):
        graph = RunGraph()
        graph.seed(dict(walkable_cells=[dict(position=dict(x=0, y=0), weight=1),
                                        dict(position=dict(x=5, y=5), weight=1)]))
        _, _, trials, _ = GridSearch().tune(graph.view(), (0, 0), (5, 5), 'l1', 1.0)
        self.assertTrue(all(t['score'] is None and not t['found'] for t in trials))

    def test_parameter_validation(self):
        for optimizer, values in ((GridSearch, {'weight_min': 3, 'weight_max': 2}),
                                  (GridSearch, {'weight_step': 0.1, 'weight_max': 20}),
                                  (RandomSearch, {'trials': 0}), (HillClimbing, {'bogus': 1}),
                                  (RandomSearch, {'seed': True}), (GridSearch, {'lock_heuristic': 0.5}),
                                  (RandomSearch, {'weight_min': 6}), (HillClimbing, {'weight_min': 6}),
                                  (GridSearch, {'cost_weight': 0, 'time_weight': 0, 'memory_weight': 0})):
            with self.subTest(optimizer=optimizer.__name__, values=values):
                with self.assertRaises(ValueError):
                    optimizer.resolve(values)
        self.assertEqual(RandomSearch.resolve({})['trials'], 20)
