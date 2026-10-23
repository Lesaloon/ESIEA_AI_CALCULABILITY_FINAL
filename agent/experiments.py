"""Reproducible parameter searches on immutable, shared scenario snapshots."""

import asyncio
import random
import threading
import gc
import multiprocessing
import os
import tracemalloc
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from itertools import product
from statistics import fmean, median, pstdev
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from agent.memory import RunGraph
from agent.registry import ALGORITHMS

Heuristic = Literal['zero', 'l1', 'l2', 'squared_l2', 'mse', 'linf']


class ScoreWeights(BaseModel):
    """Relative importance of each efficiency criterion; normalized when scoring."""

    time: float = Field(default=40, ge=0, allow_inf_nan=False)
    memory: float = Field(default=40, ge=0, allow_inf_nan=False)
    quality: float = Field(default=20, ge=0, allow_inf_nan=False)
    expanded: float = Field(default=0, ge=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def nonzero_total(self):
        import math
        if not 0 < self.total() < math.inf:
            raise ValueError('At least one score weight must be positive and their sum must be finite')
        return self

    def total(self):
        return self.time + self.memory + self.quality + self.expanded


class ExperimentConfiguration(BaseModel):
    """Validated search space, scenario generator and measurement settings."""

    # Parameter trials choose an algorithm, a heuristic and its multiplier w.
    algorithms: list[Literal['astar', 'dijkstra']] = Field(default=['astar', 'dijkstra'], min_length=1, max_length=2)
    methods: list[Literal['grid', 'random']] = Field(default=['grid', 'random'], max_length=2)
    heuristics: list[Heuristic] = Field(default=['l1', 'l2', 'linf'], max_length=6)
    weight_space: Literal['list', 'range'] = 'list'
    weight_start: float = Field(default=0.5, ge=0, le=1000, allow_inf_nan=False)
    weight_end: float = Field(default=2, ge=0, le=1000, allow_inf_nan=False)
    weight_step: float = Field(default=0.5, gt=0, le=1000, allow_inf_nan=False)
    weights: list[float] = Field(default=[0.5, 1, 1.5, 2], min_length=1)
    random_space: Literal['discrete', 'continuous'] = 'discrete'
    weight_min: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)
    weight_max: float = Field(default=3, ge=0, le=1000, allow_inf_nan=False)
    random_trials: int = Field(default=8, ge=1, le=180, strict=True)
    seed: int = Field(default=42, ge=0, le=2147483647, strict=True)
    # Map randomness is independent of the random parameter search below.
    map_source: Literal['current', 'random'] = 'current'
    map_count: int = Field(default=10, ge=1, le=50, strict=True)
    size: int = Field(default=10, ge=3, le=20, strict=True)
    obstacle_density: float = Field(default=0.2, ge=0, le=0.7, allow_inf_nan=False)
    cell_weight_min: int = Field(default=1, ge=1, le=9, strict=True)
    cell_weight_max: int = Field(default=9, ge=1, le=9, strict=True)
    objective: Literal['cost', 'expanded', 'time_ms', 'memory_kib', 'score'] = 'cost'
    score_weights: ScoreWeights = Field(default_factory=ScoreWeights)
    timing_repeats: int = Field(default=3, ge=1, strict=True)

    @model_validator(mode='after')
    def validate_space(self):
        """Check relationships between fields after individual field validation."""
        import math
        if 'astar' in self.algorithms and (not self.methods or not self.heuristics):
            raise ValueError('A* requires at least one search method and one heuristic')
        if any(not math.isfinite(w) or not 0 <= w <= 1000 for w in self.weights):
            raise ValueError('Heuristic weights must be finite and between 0 and 1000')
        if self.weight_min > self.weight_max or self.cell_weight_min > self.cell_weight_max:
            raise ValueError('Minimum weights must not exceed maximum weights')
        for name in ('algorithms', 'methods', 'heuristics', 'weights'):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f'{name} must not contain duplicates')
        # Also validate range ordering and whether its step yields distinct floats.
        discrete_weights(self)
        return self


def discrete_weights(config):
    """Generate A + k*C <= B using decimal arithmetic (no drifting endpoints)."""
    if config.weight_space == 'list':
        return list(config.weights)
    start, end, step = (Decimal(str(value)) for value in
                        (config.weight_start, config.weight_end, config.weight_step))
    if end < start:
        raise ValueError('B (end) must be greater than or equal to A (start)')
    count = int((end - start) // step) + 1
    # Include B only when the step lands on it; never overshoot the interval.
    weights = [float(start + i * step) for i in range(count)]
    if len(set(weights)) != len(weights):
        raise ValueError('C (step) is too small to produce distinct weights')
    return weights


def candidates(config):
    """Method-specific ordered trials; Dijkstra is a separate shared baseline."""
    if 'astar' not in config.algorithms:
        return []
    space = list(product(config.heuristics, discrete_weights(config)))
    # A local RNG makes parameter draws repeatable without affecting map draws.
    rng = random.Random(config.seed)
    trials = []
    for method in config.methods:
        if method == 'grid':
            selected = space
        elif config.random_space == 'discrete':
            # Sampling without replacement avoids wasting trials on duplicates.
            selected = rng.sample(space, min(config.random_trials, len(space)))
        elif config.weight_min == config.weight_max:
            # A collapsed continuous interval has only one weight per heuristic.
            selected = [(h, config.weight_min) for h in rng.sample(config.heuristics, len(config.heuristics))]
            selected = selected[:config.random_trials]
        else:
            selected = [(rng.choice(config.heuristics), rng.uniform(config.weight_min, config.weight_max))
                        for _ in range(config.random_trials)]
        trials.extend(dict(method=method, trial=i + 1, algorithm='astar', heuristic=h, heuristic_weight=w)
                      for i, (h, w) in enumerate(selected))
    return trials


def graph_from(snapshot):
    """Rebuild the agent's eight-neighbor movement graph from a frozen map."""
    graph = RunGraph()
    graph.seed(snapshot['grid'])
    return graph.view()


def reachable(graph, start):
    """Find a connected component with an iterative depth-first traversal."""
    seen, pending = {start}, [start]
    while pending:
        for neighbor in graph.edges[pending.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return sorted(seen)


def random_scenario(config, rng):
    """Choose endpoints in a connected component; never carve away obstacles."""
    for _ in range(100):
        cells = [dict(position=dict(x=x, y=y), weight=rng.randint(config.cell_weight_min, config.cell_weight_max))
                 for y in range(config.size) for x in range(config.size)
                 if rng.random() >= config.obstacle_density]
        snapshot = dict(grid=dict(width=config.size, height=config.size, walkable_cells=cells))
        graph = graph_from(snapshot)
        remaining = set(graph.weights)
        components = []
        # Endpoints must be distinct and connected; isolated cells cannot qualify.
        while remaining:
            component = reachable(graph, min(remaining))
            remaining.difference_update(component)
            if len(component) >= 2:
                components.append(component)
        if components:
            component = rng.choice(components)
            start, goal = rng.sample(component, 2)
            snapshot.update(start=dict(x=start[0], y=start[1]), goal=dict(x=goal[0], y=goal[1]))
            return snapshot
    raise ValueError('Could not generate a connected scenario; reduce obstacle density')


def evaluate(graph, start, goal, trial):
    """Time one fresh search, excluding algorithm construction and metric extraction."""
    algorithm = ALGORITHMS[trial['algorithm']].factory(trial['heuristic'], trial['heuristic_weight'])
    started = perf_counter()
    result = algorithm.search(graph, start, goal)
    elapsed = (perf_counter() - started) * 1000
    success = bool(result.path)
    # Each edge charges entry into its destination; initial placement costs zero.
    cost = sum(graph.edges[a][b] for a, b in zip(result.path, result.path[1:])) if success else None
    return dict(success=success, cost=cost, length=len(result.path) - 1 if success else None,
                expanded=len(result.trace.expanded), time_ms=elapsed)


def smooth_timings(samples):
    """Mean after a Hampel-style filter, with a 25% floor for tiny timings."""
    center = median(samples)
    mad = median(abs(value - center) for value in samples)
    # Scale MAD to a robust spread estimate. The relative floor avoids rejecting
    # small variations when most readings are identical or extremely short.
    threshold = max(3 * 1.4826 * mad, 0.25 * center)
    # Fewer than three observations cannot identify an isolated outlier.
    outliers = [i for i, value in enumerate(samples)
                if len(samples) >= 3 and abs(value - center) > threshold]
    rejected = set(outliers)
    kept = [value for i, value in enumerate(samples) if i not in rejected]
    return dict(time_ms=fmean(kept), time_mean_raw_ms=fmean(samples),
                time_samples_ms=list(samples), time_used_samples_ms=kept,
                time_outlier_indices=outliers, time_std_ms=pstdev(kept),
                time_min_ms=min(kept), time_max_ms=max(kept),
                timing_runs=len(samples), timing_outliers=len(outliers))


def benchmark_scenario(snapshot, trial, repeats):
    """Run only in the dedicated worker: timing and traced memory are separate."""
    graph = graph_from(snapshot)
    start, goal = (snapshot['start']['x'], snapshot['start']['y']), (snapshot['goal']['x'], snapshot['goal']['y'])
    started = perf_counter()
    # Warm imports/caches equally for every configuration, outside the samples.
    evaluate(graph, start, goal, trial)
    samples = [evaluate(graph, start, goal, trial) for _ in range(repeats)]
    value = samples[0].copy()
    value.update(smooth_timings([sample['time_ms'] for sample in samples]))
    # Measure Python allocation peaks in an extra run: tracemalloc's overhead
    # must not contaminate the timing samples. The graph was allocated earlier.
    algorithm = ALGORITHMS[trial['algorithm']].factory(trial['heuristic'], trial['heuristic_weight'])
    gc.collect()
    tracemalloc.start()
    try:
        # Keep the result alive until after the peak is read (includes telemetry).
        result = algorithm.search(graph, start, goal)
        _, peak = tracemalloc.get_traced_memory()
        value['memory_kib'] = peak / 1024
        del result
    finally:
        tracemalloc.stop()
    return dict(**value, benchmark_ms=(perf_counter() - started) * 1000, worker_pid=os.getpid())


def efficiency_scores(value, reference, weights):
    """Dimensionless scores relative to Dijkstra on the very same map."""
    def resource(metric):
        # Lower resource usage scores higher: equal to Dijkstra gives 50/100.
        total = reference[metric] + value[metric]
        return 100 * (reference[metric] / total) if total else 50.0

    if not value['success']:
        return dict(score_time=0.0, score_memory=0.0, score_quality=0.0, score_expanded=0.0, score=0.0)
    # Optimal paths get 100 for quality; a zero-cost successful path does too.
    quality = (min(100.0, 100 * reference['cost'] / value['cost']) if value['cost'] else 100.0)
    parts = dict(score_time=resource('time_ms'), score_memory=resource('memory_kib'),
                 score_quality=quality, score_expanded=resource('expanded'))
    parts['score'] = weighted_score(parts, weights)
    return parts


def weighted_score(parts, weights):
    """Combine component scores into a weighted average to maximize."""
    total = weights.total()
    return sum(parts[f'score_{name}'] * (weight / total) for name, weight in weights.model_dump().items())


def rank_key(row, objective):
    # Failures can never outrank successful configurations.
    value = -row['score'] if objective == 'score' else row[objective]
    return (-row['success_rate'], value if value is not None else float('inf'),
            row['expanded'], row['time_ms'])


class ExperimentManager:
    """Own one in-memory experiment and publish progress to API consumers."""

    def __init__(self):
        self.job = None
        self.task = None
        self.cancel_event = threading.Event()
        self.lock = asyncio.Lock()

    def snapshot(self, details=False):
        """Build rankings and best-so-far curves; include raw data only on request."""
        if not self.job:
            return None
        job = self.job
        rows = sorted(job['results'], key=lambda row: rank_key(row, job['config']['objective']))
        methods = []
        for method in job['config']['methods']:
            configurations = [row for row in rows if row['method'] == method]
            evaluations = [row for row in job['evaluations'] if row['method'] == method]
            methods.append(dict(method=method, configurations=len(configurations), evaluations=len(evaluations),
                                search_ms=sum(row['time_ms'] for row in evaluations),
                                benchmark_ms=sum(row['benchmark_ms'] for row in evaluations),
                                timing_runs=sum(row['timing_runs'] for row in evaluations),
                                timing_outliers=sum(row['timing_outliers'] for row in evaluations),
                                best=configurations[0] if configurations else None))
        algorithms = []
        for algorithm in ALGORITHMS:
            configurations = [row for row in rows if row['algorithm'] == algorithm]
            if configurations:
                best = min(configurations, key=lambda row: rank_key(row, 'score'))
                algorithms.append(dict(algorithm=algorithm, label=ALGORITHMS[algorithm].label,
                                       configurations=len(configurations), best=best))
        algorithms.sort(key=lambda row: rank_key(row['best'], 'score'))
        curves = {}
        # Curves follow trial order rather than rank, showing search progress.
        for method in job['config']['methods']:
            best, points = None, []
            for row in sorted((r for r in rows if r['method'] == method), key=lambda r: r['trial']):
                if best is None or rank_key(row, job['config']['objective']) < rank_key(best, job['config']['objective']):
                    best = row
                points.append(dict(trial=row['trial'], best=best[job['config']['objective']], success_rate=best['success_rate']))
            curves[method] = points
        return {**{k: v for k, v in job.items() if details or k not in ('evaluations', 'scenarios')},
                'results': rows, 'method_summaries': methods, 'algorithm_summaries': algorithms, 'curves': curves}

    def rescore(self, weights):
        """Reuse measured component scores without running the searches again."""
        if not self.job:
            raise ValueError('No experiment available')
        if self.job['status'] == 'running':
            raise ValueError('Wait until the experiment finishes before changing its scoring weights')
        self.job['config']['score_weights'] = weights.model_dump()
        grouped = {}
        for value in self.job['evaluations']:
            value['score'] = weighted_score(value, weights)
            grouped.setdefault((value['method'], value['trial']), []).append(value['score'])
        for row in self.job['results']:
            scores = grouped[(row['method'], row['trial'])]
            row['score'] = sum(scores) / len(scores)
        return self.snapshot()

    async def start(self, config, client):
        """Capture the current map when requested and schedule a background job."""
        async with self.lock:
            # Serialize job creation so simultaneous requests cannot start two jobs.
            if self.task and not self.task.done():
                raise ValueError('An experiment is already running')
            scenarios = [await client.scenario_snapshot()] if config.map_source == 'current' else None
            self.cancel_event = threading.Event()
            trials = candidates(config)
            count = len(scenarios) if scenarios else config.map_count
            self.job = dict(id=str(uuid4()), status='running', error='', config=config.model_dump(),
                            weight_values=discrete_weights(config),
                            # One shared Dijkstra reference per map, plus each trial.
                            completed=0, total=(len(trials) + 1) * count, results=[], evaluations=[],
                            curves={method: [] for method in config.methods}, scenarios=[], elapsed_ms=0)
            self.task = asyncio.create_task(self.run(config, scenarios, trials))
            return self.snapshot()

    async def cancel(self):
        """Request cancellation between measurements and wait for worker cleanup."""
        async with self.lock:
            self.cancel_event.set()
            if self.task:
                await self.task
            return self.snapshot()

    async def measure(self, snapshot, trial, repeats):
        # CPU work runs outside the API process so its event loop stays responsive.
        return await asyncio.get_running_loop().run_in_executor(self.pool, benchmark_scenario, snapshot, trial, repeats)

    async def run(self, config, scenarios, trials):
        """Evaluate every configuration on the same maps, then aggregate metrics."""
        started = perf_counter()
        job = self.job
        baseline = dict(method='baseline', trial=0, algorithm='dijkstra', heuristic='zero', heuristic_weight=0)
        # A single spawned worker isolates tracemalloc and avoids benchmark
        # configurations competing against one another for CPU resources.
        self.pool = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context('spawn'))
        try:
            if scenarios is None:
                # Use a separate RNG with the same seed: changing the trial budget
                # does not change which maps are generated.
                rng = random.Random(config.seed)
                scenarios = []
                for _ in range(config.map_count):
                    if self.cancel_event.is_set():
                        break
                    scenarios.append(await asyncio.to_thread(random_scenario, config, rng))
            job['scenarios'] = scenarios
            references = {}
            # Finish all Dijkstra measurements first; each map needs its own
            # optimal cost and resource baseline before scoring any A* trial.
            for trial in [baseline, *trials]:
                values = []
                for index, scenario in enumerate(scenarios):
                    if self.cancel_event.is_set():
                        break
                    value = await self.measure(scenario, trial, config.timing_repeats)
                    if trial['method'] == 'baseline':
                        references[index] = value.copy()
                    optimum = references[index]['cost']
                    value['gap_percent'] = (100 * (value['cost'] - optimum) / optimum
                                            if value['success'] and optimum else
                                            0.0 if value['success'] and optimum == 0 else None)
                    value.update(efficiency_scores(value, references[index], config.score_weights))
                    job['evaluations'].append(dict(**trial, map_index=index, **value))
                    job['completed'] += 1
                    job['elapsed_ms'] = (perf_counter() - started) * 1000
                    values.append(value)
                if self.cancel_event.is_set():
                    break
                successful = [v for v in values if v['success']]
                summary = dict(**trial, success_rate=len(successful) / len(values), maps=len(values))
                for metric in ('cost', 'length', 'gap_percent', 'expanded', 'time_ms', 'time_mean_raw_ms', 'memory_kib',
                               'score_time', 'score_memory', 'score_quality', 'score_expanded', 'score'):
                    # Failed searches have no route metrics, but still consume
                    # resources and contribute zero efficiency scores.
                    source = successful if metric in ('cost', 'length', 'gap_percent') else values
                    numbers = [v[metric] for v in source if v[metric] is not None]
                    summary[metric] = sum(numbers) / len(numbers) if numbers else None
                summary['timing_runs'] = sum(v['timing_runs'] for v in values)
                summary['timing_outliers'] = sum(v['timing_outliers'] for v in values)
                # Always expose the reference, even for A*-only searches.
                job['results'].append(summary)
            job['status'] = 'cancelled' if self.cancel_event.is_set() else 'completed'
        except Exception as exc:
            job['status'], job['error'] = 'failed', f'{type(exc).__name__}: {exc}'
        finally:
            # Wait for the current measurement without blocking the API event loop.
            await asyncio.to_thread(self.pool.shutdown, wait=True, cancel_futures=True)
            job['elapsed_ms'] = (perf_counter() - started) * 1000
