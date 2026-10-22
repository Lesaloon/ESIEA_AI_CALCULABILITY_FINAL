"""Recherche 2: the same ceiling search as Recherche 1, with a weighted score."""

from math import inf
from unittest import TestCase
from unittest.mock import patch

from agent.algorithms.grid_search import _score, weighted_score
from agent.algorithms.main_algo_2 import main_algo_2


def steady_clock():
    time = {'now': 0}

    def tick():
        time['now'] += 1
        return float(time['now'])

    return tick


class WeightedScoreTests(TestCase):
    def test_cost_counts_ten_times_the_duration(self):
        cheap = dict(cost=14, duration=1.5)
        fast = dict(cost=15, duration=1)
        self.assertEqual(weighted_score(cheap, 14, 1), 10 + 1.5)
        self.assertAlmostEqual(weighted_score(fast, 14, 1), 10 * (15 / 14) + 1)
        self.assertLess(weighted_score(cheap, 14, 1), weighted_score(fast, 14, 1))
        self.assertGreater(_score(cheap, 14, 1), _score(fast, 14, 1))

    def test_unreachable_path_stays_infinite(self):
        self.assertEqual(weighted_score(dict(cost=inf, duration=1), 1, 1), inf)


class MainAlgo2Tests(TestCase):
    def test_grid_has_one_hundred_values_and_ten_climbs(self):
        weights = [[1, 9, 1], [1, 1, 1]]
        with patch('agent.algorithms.grid_search.perf_counter', steady_clock()), \
                patch('agent.algorithms.hill_climbing.perf_counter', steady_clock()):
            report = main_algo_2(weights, (0, 0), (2, 0))
        self.assertEqual(report['ceiling'], 9 * 5)
        grid = report['grid']['trials']
        self.assertEqual(len(grid), 100)
        self.assertAlmostEqual(grid[0]['w'], 1)
        self.assertAlmostEqual(grid[-1]['w'], report['ceiling'])
        seeds = sorted(grid, key=lambda trial: (trial['score'], trial['w']))[:10]
        self.assertEqual(len(report['climbs']), 10)
        self.assertEqual(
            [climb['trials'][0]['w'] for climb in report['climbs']],
            [seed['w'] for seed in seeds],
        )
        climb = report['climbs'][0]['trials']
        self.assertAlmostEqual(climb[1]['w'] - climb[0]['w'], 0.1)
        self.assertEqual(grid[0]['score'], weighted_score(grid[0], min(trial['cost'] for trial in grid), min(trial['duration'] for trial in grid)))
        self.assertIn(report['best']['w'], [climb['best']['w'] for climb in report['climbs']])

    def test_single_cell_climbs_the_only_weight(self):
        with patch('agent.algorithms.grid_search.perf_counter', steady_clock()), \
                patch('agent.algorithms.hill_climbing.perf_counter', steady_clock()):
            report = main_algo_2([[1]], (0, 0), (0, 0))
        self.assertEqual(len(report['grid']['trials']), 1)
        self.assertEqual(len(report['climbs']), 1)
        self.assertEqual(report['best']['w'], 1)
