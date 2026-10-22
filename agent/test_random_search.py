"""Random search over weighted A*."""

from math import inf
from unittest import TestCase

from agent.algorithms.random_search import _samples, random_search
from agent.models import GraphView


def sample_graph():
    edges = {
        (0, 0): {(1, 0): 5.0, (0, 1): 1.0},
        (0, 1): {(1, 0): 1.0},
        (1, 0): {},
    }
    return GraphView(edges, {}, frozenset())


class RandomSearchTests(TestCase):
    def test_default_draw_is_ten_values_between_one_and_fifty(self):
        values = _samples(1, 50, 10, seed=1)
        self.assertEqual(len(values), 10)
        self.assertTrue(all(1 <= value <= 50 for value in values))

    def test_same_seed_draws_the_same_values(self):
        self.assertEqual(_samples(1, 50, 10, seed=3), _samples(1, 50, 10, seed=3))

    def test_bounds_and_count_are_checked(self):
        graph = sample_graph()
        for low, high, count in ((0, 50, 10), (1, 0.5, 10), (5, 2, 10), (1, inf, 10), (1, 50, 0)):
            with self.subTest(low=low, high=high, count=count):
                with self.assertRaises(ValueError):
                    random_search(graph, (0, 0), (1, 0), low=low, high=high, count=count, seed=1)

    def test_each_draw_records_cost_and_duration(self):
        report = random_search(sample_graph(), (0, 0), (1, 0), low=1, high=3, count=4, seed=2)
        self.assertEqual(len(report['trials']), 4)
        self.assertTrue(all(1 <= trial['w'] <= 3 for trial in report['trials']))
        self.assertTrue(all(trial['cost'] in (2, 5) for trial in report['trials']))
        self.assertTrue(all(trial['duration'] >= 0 for trial in report['trials']))
        self.assertIn(report['best'], report['trials'])
