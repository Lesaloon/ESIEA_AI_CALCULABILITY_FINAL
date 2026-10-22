"""Grid search up to the map ceiling, then hill climbing."""

from math import inf
from unittest import TestCase
from unittest.mock import patch

from agent.algorithms.main_algo_1 import main_algo_1, weight_ceiling


def steady_clock():
    time = {'now': 0}

    def tick():
        time['now'] += 1
        return float(time['now'])

    return tick


class WeightCeilingTests(TestCase):
    def test_ceiling_is_the_most_expensive_simple_path(self):
        self.assertEqual(weight_ceiling([[1, 9, None], [1, 1, 1]]), 9 * 4)

    def test_ceiling_is_at_least_one(self):
        self.assertEqual(weight_ceiling([[1]]), 1)
        self.assertEqual(weight_ceiling([[0]]), 1)

    def test_map_must_be_a_rectangle_with_a_walkable_cell(self):
        for weights in ([], [[1], [1, 2]], [[None]], [[1, inf]]):
            with self.subTest(weights=weights):
                with self.assertRaises(ValueError):
                    weight_ceiling(weights)


class MainAlgo1Tests(TestCase):
    def test_grid_has_one_hundred_values_and_ten_climbs(self):
        weights = [[1, 9, 1], [1, 1, 1]]
        with patch('agent.algorithms.grid_search.perf_counter', steady_clock()), \
                patch('agent.algorithms.hill_climbing.perf_counter', steady_clock()):
            report = main_algo_1(weights, (0, 0), (2, 0))
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
        self.assertIn(report['best']['w'], [climb['best']['w'] for climb in report['climbs']])

    def test_single_cell_climbs_the_only_weight(self):
        with patch('agent.algorithms.grid_search.perf_counter', steady_clock()), \
                patch('agent.algorithms.hill_climbing.perf_counter', steady_clock()):
            report = main_algo_1([[1]], (0, 0), (0, 0))
        self.assertEqual(len(report['grid']['trials']), 1)
        self.assertEqual(len(report['climbs']), 1)
        self.assertEqual(report['best']['w'], 1)
