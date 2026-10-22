"""Hill climbing over weighted A*."""

from math import inf
from unittest import TestCase
from unittest.mock import patch

from agent.algorithms.grid_search import _score
from agent.algorithms.hill_climbing import hill_climbing
from agent.models import GraphView


def sample_graph():
    edges = {
        (0, 0): {(1, 0): 5.0, (0, 1): 1.0},
        (0, 1): {(1, 0): 1.0},
        (1, 0): {},
    }
    return GraphView(edges, {}, frozenset())


def steady_clock():
    time = {'now': 0}

    def tick():
        time['now'] += 1
        return float(time['now'])

    return tick


class HillClimbingTests(TestCase):
    def test_parameters_are_checked(self):
        graph = sample_graph()
        for w, step, limit in ((0, 1, 10), (inf, 1, 10), (1, 0, 10), (1, 1, 0), (1, 1, False)):
            with self.subTest(w=w, step=step, limit=limit):
                with self.assertRaises(ValueError):
                    hill_climbing(graph, (0, 0), (1, 0), w=w, step=step, limit=limit)

    def test_equal_durations_move_toward_the_cheaper_weight_then_stop(self):
        with patch('agent.algorithms.hill_climbing.perf_counter', steady_clock()):
            report = hill_climbing(sample_graph(), (0, 0), (1, 0), w=3, step=1)
        self.assertEqual(report['best']['w'], 2)
        self.assertEqual(report['best']['cost'], 2)
        self.assertEqual([trial['w'] for trial in report['trials']], [3, 4, 2, 1])
        self._assert_local_minimum(report, step=1)

    def test_neighbor_below_one_is_ignored(self):
        with patch('agent.algorithms.hill_climbing.perf_counter', steady_clock()):
            report = hill_climbing(sample_graph(), (0, 0), (1, 0), w=1, step=1)
        self.assertEqual(report['best']['w'], 1)
        self.assertEqual([trial['w'] for trial in report['trials']], [1, 2])

    def test_limit_stops_the_walk_before_the_local_minimum(self):
        with patch('agent.algorithms.hill_climbing.perf_counter', side_effect=[0, 0.04, 0.04, 0.06, 0.06, 0.11, 0.11, 0.12]):
            report = hill_climbing(sample_graph(), (0, 0), (1, 0), w=5, step=1, limit=2)
        self.assertEqual([trial['w'] for trial in report['trials']], [5, 6, 4, 7])
        self.assertEqual(report['best']['w'], 7)
        self.assertIn(report['best'], report['trials'])

    def _assert_local_minimum(self, report, step):
        best = report['best']
        neighbors = [
            trial for trial in report['trials']
            if abs(trial['w'] - best['w'] - step) < 1e-9 or abs(best['w'] - trial['w'] - step) < 1e-9
        ]
        self.assertTrue(neighbors)
        group = [best, *neighbors]
        best_cost = min(trial['cost'] for trial in group)
        best_duration = min(trial['duration'] for trial in group)
        best_score = _score(best, best_cost, best_duration)
        for neighbor in neighbors:
            self.assertLessEqual(best_score, _score(neighbor, best_cost, best_duration))
