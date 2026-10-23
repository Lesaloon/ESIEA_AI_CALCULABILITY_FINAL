"""Recherche 2: the same ceiling search as Recherche 1, scored against a fixed A* reference."""

from math import inf
from unittest import TestCase
from unittest.mock import patch

from agent.algorithms.grid_search import graph_from_weights, importance, reference_score, run_trial
from agent.algorithms.main_algo_2 import TIMING_REPEATS, main_algo_2


def steady_clock():
    time = {'now': 0}

    def tick():
        time['now'] += 1
        return float(time['now'])

    return tick


class ReferenceScoreTests(TestCase):
    def test_equal_trial_matches_the_reference_on_cost_and_duration(self):
        reference = dict(cost=14, duration=1, memory=8)
        same = dict(cost=14, duration=1, memory=40)
        self.assertEqual(reference_score(same, reference), 2)
        self.assertEqual(reference_score(same, reference, c=1), 2 + 40 / 8)

    def test_cost_and_duration_use_the_fixed_reference(self):
        reference = dict(cost=14, duration=2, memory=1)
        trial = dict(cost=21, duration=1, memory=1)
        self.assertEqual(reference_score(trial, reference), 21 / 14 + 0.5)
        self.assertEqual(reference_score(trial, reference, a=10, b=1), 10 * (21 / 14) + 0.5)

    def test_default_memory_importance_leaves_the_score_unchanged(self):
        reference = dict(cost=4, duration=2, memory=1)
        light = dict(cost=4, duration=2, memory=1)
        heavy = dict(cost=4, duration=2, memory=50)
        self.assertEqual(reference_score(light, reference), reference_score(heavy, reference))

    def test_unreachable_path_stays_infinite(self):
        self.assertEqual(reference_score(dict(cost=inf, duration=1, memory=1), dict(cost=1, duration=1, memory=1)), inf)

    def test_zero_reference_matches_a_zero_trial_and_rejects_a_worse_one(self):
        reference = dict(cost=0, duration=0, memory=0)
        self.assertEqual(reference_score(dict(cost=0, duration=0, memory=0), reference), 0)
        self.assertEqual(reference_score(dict(cost=1, duration=0, memory=0), reference), inf)

    def test_importances_must_be_finite_and_not_all_zero(self):
        self.assertEqual(importance(1, 1, 0), (1.0, 1.0, 0.0))
        for values in ((-1, 1, 0), (1, inf, 0), (0, 0, 0), (True, 1, 0)):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    importance(*values)


class MainAlgo2Tests(TestCase):
    def test_grid_has_one_hundred_values_and_ten_climbs(self):
        weights = [[1, 9, 1], [1, 1, 1]]
        with patch('agent.algorithms.grid_search.perf_counter', steady_clock()):
            report = main_algo_2(weights, (0, 0), (2, 0))
        self.assertEqual(report['ceiling'], 9 * 5)
        self.assertEqual(report['importance'], dict(a=1.0, b=1.0, c=0.0))
        self.assertEqual(report['reference']['w'], 1.0)
        self.assertIn('memory', report['reference'])
        grid = report['grid']['trials']
        self.assertEqual(len(grid), 100)
        self.assertAlmostEqual(grid[0]['w'], 1)
        self.assertAlmostEqual(grid[-1]['w'], report['ceiling'])
        self.assertEqual(grid[0]['score'], reference_score(grid[0], report['reference']))
        self.assertEqual(grid[0]['score'], 2)
        self.assertTrue(all('memory' in trial for trial in grid))
        seeds = sorted(grid, key=lambda trial: (trial['score'], trial['w']))[:10]
        self.assertEqual(len(report['climbs']), 10)
        self.assertEqual(
            [climb['trials'][0]['w'] for climb in report['climbs']],
            [seed['w'] for seed in seeds],
        )
        climb = report['climbs'][0]['trials']
        self.assertAlmostEqual(climb[1]['w'] - climb[0]['w'], 0.1)
        self.assertEqual(climb[0]['score'], reference_score(climb[0], report['reference']))
        self.assertIn(report['best']['w'], [climb['best']['w'] for climb in report['climbs']])

    def test_single_cell_climbs_the_only_weight(self):
        with patch('agent.algorithms.grid_search.perf_counter', steady_clock()):
            report = main_algo_2([[1]], (0, 0), (0, 0))
        self.assertEqual(len(report['grid']['trials']), 1)
        self.assertEqual(len(report['climbs']), 1)
        self.assertEqual(report['best']['w'], 1)
        self.assertEqual(report['best']['score'], reference_score(report['best'], report['reference']))

    def test_duration_is_the_median_of_three_runs(self):
        self.assertEqual(TIMING_REPEATS, 3)
        clock = iter([0, 0.05, 0.05, 0.06, 0.06, 0.16])
        graph = graph_from_weights([[1, 1]])
        with patch('agent.algorithms.grid_search.perf_counter', lambda: next(clock)):
            trial = run_trial(graph, (0, 0), (1, 0), 'l1', 1, memory=True, timing_repeats=TIMING_REPEATS)
        self.assertAlmostEqual(trial['duration'], 0.05)
        self.assertIn('memory', trial)

    def test_recherche_2_times_every_search_three_times(self):
        calls = {'n': 0}

        def tick():
            calls['n'] += 1
            return float(calls['n'])

        with patch('agent.algorithms.grid_search.perf_counter', tick):
            main_algo_2([[1]], (0, 0), (0, 0))
        self.assertEqual(calls['n'], 24)
