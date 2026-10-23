"""Search-space, reproducibility, weighted-cost and lifecycle regression tests."""

import asyncio
import random
import os
import tracemalloc
from dataclasses import replace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError
from agent.registry import ALGORITHMS

from agent.experiments import (ExperimentConfiguration, ExperimentManager, candidates,
                               discrete_weights, evaluate, graph_from, random_scenario, reachable,
                               benchmark_scenario, efficiency_scores, rank_key, ScoreWeights, smooth_timings)


def scenario():
    return dict(grid=dict(width=3, height=3, walkable_cells=[
        dict(position=dict(x=x, y=y), weight=9 if (x, y) == (1, 1) else 1)
        for y in range(3) for x in range(3)]), start=dict(x=0, y=0), goal=dict(x=2, y=2))


class SearchTests(TestCase):
    def test_timings_drop_a_single_spike_and_average_the_retained_runs(self):
        timing = smooth_timings([1, 1.1, 20])
        self.assertAlmostEqual(timing['time_ms'], 1.05)
        self.assertAlmostEqual(timing['time_mean_raw_ms'], 22.1 / 3)
        self.assertEqual(timing['time_samples_ms'], [1, 1.1, 20])
        self.assertEqual(timing['time_used_samples_ms'], [1, 1.1])
        self.assertEqual(timing['time_outlier_indices'], [2])
        self.assertEqual(timing['timing_runs'], 3)
        self.assertEqual(timing['timing_outliers'], 1)
        self.assertAlmostEqual(timing['time_std_ms'], .05)

    def test_timing_filter_handles_normal_variation_equal_values_and_small_samples(self):
        for samples, expected in (([1, 1.1, 1.2], 1.1), ([1, 1, 1], 1),
                                  ([1, 1, 1.1], 3.1 / 3), ([0, 0, 0], 0),
                                  ([1], 1), ([1, 10], 5.5)):
            with self.subTest(samples=samples):
                timing = smooth_timings(samples)
                self.assertAlmostEqual(timing['time_ms'], expected)
                self.assertEqual(timing['timing_outliers'], 0)
        self.assertEqual(smooth_timings([1, 1, 100])['time_ms'], 1)

    def test_benchmark_uses_smoothed_time_and_preserves_raw_runs(self):
        results = [dict(success=True, cost=3, length=3, expanded=4, time_ms=duration)
                   for duration in (100, 1, 1.1, 20)]
        with patch('agent.experiments.evaluate', side_effect=results) as evaluate_mock:
            result = benchmark_scenario(scenario(), dict(algorithm='astar', heuristic='linf', heuristic_weight=1), 3)
        self.assertEqual(evaluate_mock.call_count, 4)  # warm-up + three measured runs
        self.assertAlmostEqual(result['time_ms'], 1.05)
        self.assertEqual(result['time_samples_ms'], [1, 1.1, 20])
        self.assertEqual(result['timing_outliers'], 1)

    def test_resource_scores_are_dimensionless_and_weighted_not_added_in_raw_units(self):
        reference = dict(success=True, cost=10, time_ms=10, memory_kib=100, expanded=100)
        weights = ScoreWeights(time=1, memory=1, quality=1, expanded=0)
        baseline = efficiency_scores(reference, reference, weights)
        self.assertEqual(baseline['score_time'], 50)
        self.assertEqual(baseline['score_memory'], 50)
        self.assertEqual(baseline['score_quality'], 100)
        faster = efficiency_scores({**reference, 'time_ms': 5}, reference, weights)
        self.assertGreater(faster['score'], baseline['score'])
        cheaper_memory = efficiency_scores({**reference, 'memory_kib': 50}, reference, weights)
        self.assertGreater(cheaper_memory['score_memory'], baseline['score_memory'])
        poor_path = efficiency_scores({**reference, 'cost': 20}, reference, weights)
        self.assertEqual(poor_path['score_quality'], 50)
        failed = efficiency_scores({**reference, 'success': False, 'cost': None}, reference, weights)
        self.assertTrue(all(v == 0 for v in failed.values()))
        scaled = efficiency_scores({**reference, 'time_ms': 5000}, {**reference, 'time_ms': 10000}, weights)
        self.assertEqual(scaled['score_time'], faster['score_time'])
        self.assertEqual(efficiency_scores(reference, reference,
            ScoreWeights(time=1e308, memory=0, quality=0))['score'], 50)
        for invalid in (dict(time=0, memory=0, quality=0, expanded=0), dict(time=-1), dict(memory=float('nan'))):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                ScoreWeights(**invalid)

    def test_score_ranking_descends_and_prefers_success(self):
        row = dict(success_rate=1, score=80, expanded=10, time_ms=1)
        self.assertLess(rank_key(row, 'score'), rank_key({**row, 'score': 20}, 'score'))
        self.assertLess(rank_key(row, 'score'), rank_key({**row, 'success_rate': .5, 'score': 99}, 'score'))

    def test_memory_measurement_sees_temporary_allocations_without_tracing_timing_samples(self):
        original = ALGORITHMS['astar']
        states = []

        class AllocatingSearch:
            def __init__(self, heuristic, weight):
                self.algorithm = original.factory(heuristic, weight)

            def search(self, graph, start, goal):
                states.append(tracemalloc.is_tracing())
                scratch = bytearray(1024 * 1024)
                result = self.algorithm.search(graph, start, goal)
                del scratch
                return result

        with patch.dict(ALGORITHMS, astar=replace(original, factory=AllocatingSearch)):
            value = benchmark_scenario(scenario(), dict(algorithm='astar', heuristic='linf', heuristic_weight=1), 3)
        self.assertGreaterEqual(value['memory_kib'], 1024)
        self.assertEqual(states, [False, False, False, False, True])
        self.assertFalse(tracemalloc.is_tracing())

    def test_range_supports_start_end_step_and_weights_above_twenty(self):
        config = ExperimentConfiguration(weight_space='range', weight_start=1, weight_end=50,
                                         weight_step=1, heuristics=['linf'], random_trials=180)
        self.assertEqual(discrete_weights(config), list(range(1, 51)))
        trials = candidates(config)
        grid = [t['heuristic_weight'] for t in trials if t['method'] == 'grid']
        sampled = [t['heuristic_weight'] for t in trials if t['method'] == 'random']
        self.assertEqual(grid, list(range(1, 51)))
        self.assertEqual(len(sampled), 50)
        self.assertEqual(set(grid), set(sampled))

    def test_decimal_steps_include_aligned_endpoint_without_overshooting(self):
        for start, end, step, expected in (
                (0.1, 0.3, 0.1, [0.1, 0.2, 0.3]),
                (1, 2, 0.3, [1, 1.3, 1.6, 1.9]),
                (0, 0, 0.2, [0]),
                (2, 2.1, 1, [2]),
                (0, 199, 1, list(range(200)))):
            with self.subTest(start=start, end=end, step=step):
                config = ExperimentConfiguration(weight_space='range', weight_start=start,
                                                 weight_end=end, weight_step=step)
                self.assertEqual(discrete_weights(config), expected)

    def test_invalid_ranges_fail_before_starting_any_search(self):
        for changes in (dict(weight_start=3, weight_end=1), dict(weight_step=0), dict(weight_step=-1),
                        dict(weight_step=float('nan')), dict(weight_end=float('inf')),
                        dict(weight_start=1, weight_end=1.0000000000000002, weight_step=1e-17),
                        dict(weight_start=-1), dict(weight_end=1001)):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ExperimentConfiguration(weight_space='range', **changes)

    def test_more_than_two_hundred_weights_are_evaluated_without_truncation(self):
        config = ExperimentConfiguration(weight_space='range', weight_start=0, weight_end=1000,
                                         weight_step=0.5, heuristics=['linf'], methods=['grid'])
        weights = discrete_weights(config)
        self.assertEqual(len(weights), 2001)
        self.assertEqual(weights[0], 0)
        self.assertEqual(weights[-1], 1000)
        self.assertEqual([trial['heuristic_weight'] for trial in candidates(config)], weights)
        listed = ExperimentConfiguration(weights=weights, heuristics=['linf'], methods=['grid'])
        self.assertEqual(candidates(listed), candidates(config))

    def test_discrete_grid_and_random_are_reproducible_without_duplicates(self):
        config = ExperimentConfiguration(random_trials=180)
        trials = candidates(config)
        self.assertEqual(trials, candidates(config))
        grid = [(t['heuristic'], t['heuristic_weight']) for t in trials if t['method'] == 'grid']
        sampled = [(t['heuristic'], t['heuristic_weight']) for t in trials if t['method'] == 'random']
        self.assertEqual(len(grid), 12)
        self.assertEqual(set(grid), set(sampled))
        self.assertEqual(len(sampled), len(set(sampled)))
        self.assertNotEqual(grid, sampled)
        self.assertEqual(candidates(ExperimentConfiguration(algorithms=['dijkstra'])), [])

    def test_continuous_sampling_stays_in_range_and_degenerate_interval_is_unique(self):
        config = ExperimentConfiguration(methods=['random'], random_space='continuous',
                                         weight_min=0.25, weight_max=1.25, random_trials=30)
        trials = candidates(config)
        self.assertEqual(len(trials), 30)
        self.assertEqual(trials, candidates(config))
        self.assertTrue(all(.25 <= t['heuristic_weight'] <= 1.25 for t in trials))
        config.weight_max = config.weight_min
        self.assertEqual(len(candidates(config)), len(config.heuristics))

    def test_random_maps_are_connected_reproducible_and_preserve_weight_bounds(self):
        config = ExperimentConfiguration(obstacle_density=.7, size=10, cell_weight_min=2, cell_weight_max=4)
        first, second = random.Random(42), random.Random(42)
        for _ in range(10):
            snapshot = random_scenario(config, first)
            self.assertEqual(snapshot, random_scenario(config, second))
            graph = graph_from(snapshot)
            start, goal = tuple(snapshot['start'].values()), tuple(snapshot['goal'].values())
            self.assertNotEqual(start, goal)
            self.assertIn(goal, reachable(graph, start))
            self.assertTrue(all(2 <= w <= 4 for w in graph.weights.values()))

    def test_weight_changes_route_and_zero_weight_matches_dijkstra(self):
        graph = graph_from(scenario())
        trial = dict(algorithm='astar', heuristic='linf', heuristic_weight=1)
        optimal = evaluate(graph, (0, 0), (2, 2), trial)
        greedy = evaluate(graph, (0, 0), (2, 2), {**trial, 'heuristic_weight': 20})
        zero = evaluate(graph, (0, 0), (2, 2), {**trial, 'heuristic_weight': 0})
        reference = evaluate(graph, (0, 0), (2, 2), {**trial, 'algorithm': 'dijkstra', 'heuristic_weight': 20})
        self.assertEqual(optimal['cost'], 3)
        self.assertEqual(greedy['cost'], 10)
        self.assertEqual(zero['cost'], reference['cost'])
        self.assertEqual(zero['expanded'], reference['expanded'])
        self.assertEqual(evaluate(graph, (0, 0), (0, 0), trial)['cost'], 0)

    def test_invalid_search_spaces_are_rejected(self):
        for changes in (dict(weights=[float('nan')]), dict(weights=[-1]), dict(weights=[1, 1]),
                        dict(heuristics=[]), dict(methods=[]), dict(weight_min=3, weight_max=1),
                        dict(cell_weight_min=9, cell_weight_max=1), dict(map_count=0), dict(random_trials=2.5)):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ExperimentConfiguration(**changes)


class ExperimentLifecycleTests(IsolatedAsyncioTestCase):
    async def test_isolated_worker_records_python_peak_memory_and_smoothed_timing(self):
        manager, client = ExperimentManager(), AsyncMock()
        client.scenario_snapshot.return_value = scenario()
        await manager.start(ExperimentConfiguration(algorithms=['dijkstra'], methods=[], timing_repeats=3), client)
        await manager.task
        job = manager.snapshot(details=True)
        self.assertEqual(job['status'], 'completed', job['error'])
        value = job['evaluations'][0]
        self.assertNotEqual(value['worker_pid'], os.getpid())
        self.assertGreater(value['memory_kib'], 0)
        self.assertGreater(value['time_ms'], 0)
        self.assertGreater(value['benchmark_ms'], value['time_ms'])
        self.assertEqual(value['timing_runs'], 3)
        self.assertEqual(len(value['time_samples_ms']), 3)
        self.assertAlmostEqual(value['time_ms'], sum(value['time_used_samples_ms']) / len(value['time_used_samples_ms']))
        self.assertEqual(value['score_time'], 50)
        self.assertEqual(value['score_memory'], 50)
        self.assertEqual(value['score_quality'], 100)
        self.assertAlmostEqual(value['score'], 60)
        self.assertEqual(job['algorithm_summaries'][0]['algorithm'], 'dijkstra')

    async def test_rescoring_reuses_measurements_and_updates_ranks_and_curves(self):
        manager, client = ExperimentManager(), AsyncMock()
        client.scenario_snapshot.return_value = scenario()

        async def fixed_measure(snapshot, trial, repeats):
            value = evaluate(graph_from(snapshot), (0, 0), (2, 2), trial)
            greedy = trial['heuristic_weight'] == 20
            return {**value, 'time_ms': 1 if greedy else 10, 'memory_kib': 1000 if greedy else 10,
                    'benchmark_ms': 30, 'worker_pid': -1,
                    **smooth_timings([1 if greedy else 10] * repeats)}

        with patch.object(manager, 'measure', side_effect=fixed_measure) as measure:
            await manager.start(ExperimentConfiguration(methods=['grid'], weights=[20, 1], heuristics=['linf'],
                objective='score', score_weights=ScoreWeights(time=1, memory=0, quality=0)), client)
            await manager.task
            before = manager.snapshot(details=True)
            self.assertEqual(before['results'][0]['heuristic_weight'], 20)
            after = manager.rescore(ScoreWeights(time=0, memory=1, quality=0))
            self.assertNotEqual(after['results'][0]['heuristic_weight'], 20)
            self.assertGreater(after['curves']['grid'][1]['best'], after['curves']['grid'][0]['best'])
            self.assertEqual(measure.await_count, 3)
            self.assertEqual(before['evaluations'][0]['time_ms'], manager.job['evaluations'][0]['time_ms'])

    async def test_range_configuration_and_actual_values_are_preserved_for_export(self):
        manager, client = ExperimentManager(), AsyncMock()
        client.scenario_snapshot.return_value = scenario()
        await manager.start(ExperimentConfiguration(weight_space='range', weight_start=0.1,
            weight_end=0.3, weight_step=0.1, methods=['grid'], heuristics=['linf']), client)
        await manager.task
        job = manager.snapshot(details=True)
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['weight_values'], [0.1, 0.2, 0.3])
        self.assertEqual(job['config']['weight_step'], 0.1)
        self.assertEqual(job['completed'], 4)
        self.assertEqual([r['heuristic_weight'] for r in job['evaluations'] if r['method'] == 'grid'], [0.1, 0.2, 0.3])

    async def test_shared_maps_baseline_gaps_exports_and_ranking(self):
        manager = ExperimentManager()
        client = AsyncMock()
        client.scenario_snapshot.return_value = scenario()
        await manager.start(ExperimentConfiguration(heuristics=['linf'], weights=[20, 1], random_trials=2), client)
        await manager.task
        job = manager.snapshot(details=True)
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['completed'], job['total'])
        self.assertEqual(job['completed'], 5)
        client.scenario_snapshot.assert_awaited_once()
        self.assertEqual(len(job['scenarios']), 1)
        self.assertEqual(sum(r['method'] == 'baseline' for r in job['results']), 1)
        self.assertEqual(job['results'][0]['cost'], 3)
        greedy = next(r for r in job['results'] if r['heuristic_weight'] == 20)
        self.assertAlmostEqual(greedy['gap_percent'], 700 / 3)
        self.assertEqual([p['best'] for p in job['curves']['grid']], [10, 3])
        self.assertEqual([m['evaluations'] for m in job['method_summaries']], [2, 2])
        self.assertNotIn('scenarios', manager.snapshot())
        self.assertNotIn('evaluations', manager.snapshot())

    async def test_unreachable_and_start_equal_goal(self):
        manager, client = ExperimentManager(), AsyncMock()
        snapshot = scenario()
        snapshot['grid']['walkable_cells'] = [snapshot['grid']['walkable_cells'][0], snapshot['grid']['walkable_cells'][-1]]
        client.scenario_snapshot.return_value = snapshot
        config = ExperimentConfiguration(methods=['grid'], heuristics=['linf'], weights=[1])
        await manager.start(config, client)
        await manager.task
        self.assertTrue(all(r['success_rate'] == 0 and r['cost'] is None for r in manager.snapshot()['results']))
        self.assertTrue(all(r['score'] == 0 for r in manager.snapshot()['results']))
        snapshot['goal'] = snapshot['start']
        await manager.start(config, client)
        await manager.task
        self.assertTrue(all(r['cost'] == 0 and r['gap_percent'] == 0 for r in manager.snapshot()['results']))

    async def test_cancel_and_concurrent_start_preserve_completed_evaluations(self):
        manager, client = ExperimentManager(), AsyncMock()
        client.scenario_snapshot.return_value = scenario()
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow_measure(snapshot, trial, repeats):
            entered.set()
            await release.wait()
            return benchmark_scenario(snapshot, trial, repeats)

        with patch.object(manager, 'measure', side_effect=slow_measure):
            await manager.start(ExperimentConfiguration(), client)
            try:
                await asyncio.wait_for(entered.wait(), 5)
                with self.assertRaises(ValueError):
                    await manager.start(ExperimentConfiguration(), client)
                with self.assertRaises(ValueError):
                    manager.rescore(ScoreWeights())
                cancelled = asyncio.create_task(manager.cancel())
                await asyncio.sleep(0)
                release.set()
                await cancelled
            finally:
                release.set()
                await manager.task
        job = manager.snapshot(details=True)
        self.assertEqual(job['status'], 'cancelled')
        self.assertEqual(job['completed'], 1)
        self.assertEqual(len(job['evaluations']), 1)

    async def test_random_mode_does_not_contact_environment(self):
        manager, client = ExperimentManager(), AsyncMock()
        config = ExperimentConfiguration(map_source='random', map_count=3, size=3,
                                         algorithms=['dijkstra'], methods=[], heuristics=[])
        await manager.start(config, client)
        await manager.task
        client.scenario_snapshot.assert_not_awaited()
        self.assertEqual(manager.snapshot()['status'], 'completed')
        self.assertEqual(manager.snapshot()['completed'], 3)
