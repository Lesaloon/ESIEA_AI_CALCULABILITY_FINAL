"""One weighted A* w scored across random maps."""

from unittest import TestCase
from unittest.mock import patch

from agent.algorithms.global_w_search import global_w_search


def steady_clock():
    time = {'now': 0}

    def tick():
        time['now'] += 1
        return float(time['now'])

    return tick


class GlobalWSearchTests(TestCase):
    def test_same_seed_draws_the_same_maps_and_weights(self):
        with patch('agent.algorithms.global_w_search.perf_counter', steady_clock()):
            first = global_w_search(3, 6, 11, 8, seed=7)
            second = global_w_search(3, 6, 11, 8, seed=7)
        self.assertEqual(first['seed'], 7)
        self.assertEqual(len(first['maps']), 3)
        self.assertEqual(len(first['curve']), 8)
        self.assertEqual(first['curve'][0]['w'], 1)
        self.assertAlmostEqual(first['curve'][-1]['w'], first['ceiling'])
        self.assertEqual(
            [point['w'] for point in first['curve']],
            [point['w'] for point in second['curve']],
        )
        self.assertEqual(first['maps'][0]['weights'], second['maps'][0]['weights'])
        for item in first['maps']:
            self.assertEqual(item['start'], {'x': 0, 'y': 0})
            self.assertEqual(item['goal'], {'x': 5, 'y': 5})
            self.assertIsNotNone(item['weights'][0][0])
            self.assertIsNotNone(item['weights'][5][5])
            self.assertEqual(item['obstacles'], 4)
            self.assertEqual(len(item['trials']), 8)
        best = min(first['curve'], key=lambda point: (point['score'], point['w']))
        self.assertEqual(first['best']['w'], best['w'])
        self.assertEqual(first['wins'], sum(item['best']['w'] == best['w'] for item in first['maps']))

    def test_obstacle_percentage_rounds_to_a_share_of_the_cells(self):
        with patch('agent.algorithms.global_w_search.perf_counter', steady_clock()):
            report = global_w_search(20, 10, 8, 5, seed=3)
            half = global_w_search(1, 10, 50, 5, seed=3)
        self.assertEqual(len(report['maps']), 20)
        self.assertTrue(all(item['obstacles'] == 8 for item in report['maps']))
        self.assertEqual(half['maps'][0]['obstacles'], 50)

    def test_bounds_are_rejected_before_a_map_is_drawn(self):
        for arguments in ((0, 6, 1, 5), (3, 2, 0, 5), (3, 6, 101, 5), (3, 6, 1, 4), (101, 6, 10, 5)):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    global_w_search(*arguments, seed=1)
