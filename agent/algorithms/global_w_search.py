"""Search one weighted A* w that scores well on several random maps."""

from random import Random

from agent.algorithms.grid_search import graph_from_weights, reference_score, run_trial
from agent.algorithms.main_algo_1 import weight_ceiling


def global_w_search(count, size, obstacle_percent, samples, heuristic='l1', seed=None):
    """Score the same w values on random maps and keep the best average.

    Each map is a square with random weights from 1 to 9. Obstacles are a
    percentage of its cells, rounded to the nearest count. The start and the
    goal stay at opposite corners and remain connected. Every map is scored
    against its own A* reference at w = 1, with the same formula as Recherche 2.
    The global score of a w is the average of those scores. Lower is better.
    """
    count, size, obstacles, samples = _parameters(count, size, obstacle_percent, samples)
    if seed is None:
        seed = Random().randrange(1_000_000_000)
    rng = Random(seed)
    maps = [_random_map(size, obstacles, rng) for _ in range(count)]
    ceiling = max(weight_ceiling(weights) for weights, _, _ in maps)
    candidates = _candidates(ceiling, samples)
    measured = [_measure(weights, start, goal, heuristic, candidates) for weights, start, goal in maps]
    curve = []
    for index, w in enumerate(candidates):
        group = [item['trials'][index] for item in measured]
        curve.append(dict(
            w=w,
            score=sum(trial['score'] for trial in group) / count,
            cost=sum(trial['cost'] for trial in group) / count,
            duration=sum(trial['duration'] for trial in group) / count,
            expansions=sum(trial['expansions'] for trial in group) / count,
        ))
    best = min(curve, key=lambda point: (point['score'], point['w']))
    wins = sum(1 for item in measured if item['best']['w'] == best['w'])
    return dict(seed=seed, ceiling=ceiling, best=best, wins=wins, curve=curve, maps=measured)


def _parameters(count, size, obstacle_percent, samples):
    if type(count) is not int or not 1 <= count <= 100:
        raise ValueError('count must be an integer from 1 to 100')
    if type(size) is not int or not 3 <= size <= 15:
        raise ValueError('size must be an integer from 3 to 15')
    if type(obstacle_percent) is not int or not 0 <= obstacle_percent <= 100:
        raise ValueError('obstacle percentage must be an integer from 0 to 100')
    if type(samples) is not int or not 5 <= samples <= 30:
        raise ValueError('samples must be an integer from 5 to 30')
    cells = size * size
    obstacles = min(int(obstacle_percent * cells / 100 + 0.5), cells - 2)
    return count, size, obstacles, samples


def _random_map(size, obstacles, rng):
    cells = [(x, y) for y in range(size) for x in range(size)]
    start, goal = (0, 0), (size - 1, size - 1)
    pool = [cell for cell in cells if cell not in (start, goal)]
    for _ in range(100):
        blocked = set(rng.sample(pool, obstacles))
        weights = [
            [None if (x, y) in blocked else rng.randint(1, 9) for x in range(size)]
            for y in range(size)
        ]
        if goal in _reachable(weights, start):
            return weights, start, goal
    raise ValueError('Could not draw a connected map with that many obstacles')


def _reachable(weights, start):
    height, width = len(weights), len(weights[0])
    seen = {start}
    pending = [start]
    while pending:
        x, y = pending.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                neighbor = (x + dx, y + dy)
                nx, ny = neighbor
                if neighbor in seen or not (0 <= nx < width and 0 <= ny < height):
                    continue
                if weights[ny][nx] is None:
                    continue
                seen.add(neighbor)
                pending.append(neighbor)
    return seen


def _candidates(ceiling, samples):
    if ceiling <= 1:
        return [1.0]
    return [1 + index * (ceiling - 1) / (samples - 1) for index in range(samples)]


def _measure(weights, start, goal, heuristic, candidates):
    graph = graph_from_weights(weights)
    reference = run_trial(graph, start, goal, heuristic, 1.0, memory=True)
    trials = [run_trial(graph, start, goal, heuristic, w, memory=True) for w in candidates]
    for trial in trials:
        trial['score'] = reference_score(trial, reference)
    best = min(trials, key=lambda trial: (trial['score'], trial['w']))
    return dict(
        weights=weights,
        start=dict(x=start[0], y=start[1]),
        goal=dict(x=goal[0], y=goal[1]),
        ceiling=weight_ceiling(weights),
        obstacles=sum(weight is None for row in weights for weight in row),
        best=best,
        trials=trials,
        reference=reference,
    )
