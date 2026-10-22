"""Simulated annealing over weighted A*."""

from math import inf
from unittest import TestCase
from unittest.mock import patch

from agent.algorithms.hill_climbing import hill_climbing
from agent.algorithms.simulated_annealing import simulated_annealing
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


class FixedDraw:
    def __init__(self, seed=None, value=0.9):
        self.value = value

    def uniform(self, low, high):
        return self.value

    def choice(self, values):
        return values[0]


class SimulatedAnnealingTests(TestCase):
    def test_temperature_is_checked(self):
        graph = sample_graph()
        for temperature in (-0.1, 1.1, inf):
            with self.subTest(temperature=temperature):
                with self.assertRaises(ValueError):
                    simulated_annealing(graph, (0, 0), (1, 0), temperature=temperature, limit=1)

    def test_temperature_one_follows_the_best_neighbor(self):
        graph = sample_graph()
        with patch('agent.algorithms.simulated_annealing.perf_counter', steady_clock()):
            report = simulated_annealing(graph, (0, 0), (1, 0), w=3, step=1, temperature=1)
        with patch('agent.algorithms.hill_climbing.perf_counter', steady_clock()):
            climbed = hill_climbing(graph, (0, 0), (1, 0), w=3, step=1)
        self.assertEqual(report['best']['w'], climbed['best']['w'])
        self.assertEqual([trial['w'] for trial in report['trials']], [trial['w'] for trial in climbed['trials']])

    def test_draw_above_temperature_moves_to_a_random_neighbor(self):
        with patch('agent.algorithms.simulated_annealing.perf_counter', steady_clock()), \
                patch('agent.algorithms.simulated_annealing.random.Random', FixedDraw):
            report = simulated_annealing(sample_graph(), (0, 0), (1, 0), w=2, step=1, temperature=0.2, limit=1)
        self.assertEqual([trial['w'] for trial in report['trials']], [2, 3, 1])
        self.assertEqual(report['best']['w'], 3)
        self.assertEqual(report['best']['cost'], 5)
        self.assertIn(report['best'], report['trials'])

    def test_draw_equal_to_temperature_keeps_the_best_neighbor(self):
        with patch('agent.algorithms.simulated_annealing.perf_counter', steady_clock()), \
                patch('agent.algorithms.simulated_annealing.random.Random', lambda seed=None: FixedDraw(value=0.5)):
            report = simulated_annealing(sample_graph(), (0, 0), (1, 0), w=3, step=1, temperature=0.5)
        self.assertEqual(report['best']['w'], 2)
        self.assertEqual([trial['w'] for trial in report['trials']], [3, 4, 2, 1])

    def test_same_seed_walks_the_same_weights(self):
        graph = sample_graph()
        with patch('agent.algorithms.simulated_annealing.perf_counter', steady_clock()):
            first = simulated_annealing(graph, (0, 0), (1, 0), w=4, step=1, temperature=0, limit=5, seed=1)
            second = simulated_annealing(graph, (0, 0), (1, 0), w=4, step=1, temperature=0, limit=5, seed=1)
        self.assertEqual([trial['w'] for trial in first['trials']], [trial['w'] for trial in second['trials']])
        self.assertEqual(first['best']['w'], second['best']['w'])
