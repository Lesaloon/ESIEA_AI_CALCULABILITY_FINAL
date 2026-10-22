"""Grid search over weighted A*."""

from math import inf
from unittest import TestCase

from agent.algorithms.grid_search import _weights, graph_from_weights, grid_search
from agent.models import GraphView


def sample_graph():
    edges = {
        (0, 0): {(1, 0): 5.0, (0, 1): 1.0},
        (0, 1): {(1, 0): 1.0},
        (1, 0): {},
    }
    return GraphView(edges, {}, frozenset())


class GridSearchTests(TestCase):
    def test_default_bounds_are_one_to_ten_by_one(self):
        self.assertEqual(_weights(1, 10, 1), [float(value) for value in range(1, 11)])

    def test_fractional_step_includes_the_upper_bound(self):
        values = _weights(1, 2, 0.1)
        self.assertAlmostEqual(values[0], 1)
        self.assertAlmostEqual(values[-1], 2)
        self.assertEqual(len(values), 11)

    def test_bounds_must_be_at_least_one(self):
        for low, high, step in ((0, 10, 1), (1, 0.5, 1), (1, inf, 1), (5, 2, 1), (1, 10, 0)):
            with self.subTest(low=low, high=high, step=step):
                with self.assertRaises(ValueError):
                    grid_search(sample_graph(), (0, 0), (1, 0), low=low, high=high, step=step)

    def test_each_weight_records_cost_and_duration(self):
        report = grid_search(sample_graph(), (0, 0), (1, 0), low=1, high=3, step=1)
        by_weight = {trial['w']: trial for trial in report['trials']}
        self.assertEqual(set(by_weight), {1.0, 2.0, 3.0})
        self.assertEqual(by_weight[1.0]['cost'], 2)
        self.assertEqual(by_weight[3.0]['cost'], 5)
        self.assertTrue(all(trial['duration'] >= 0 for trial in report['trials']))
        self.assertIn(report['best'], report['trials'])


class MapGridSearchTests(TestCase):
    def test_weight_matrix_uses_destination_cell_costs(self):
        graph = graph_from_weights([[1, 9, 1], [1, 1, 1]])
        report = grid_search(graph, (0, 0), (2, 0), low=1, high=1, step=1)
        self.assertEqual(report['trials'][0]['cost'], 2)
        self.assertNotIn((1, 0), report['best']['path'])
