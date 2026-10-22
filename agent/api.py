"""Browser-facing controls; all environment access goes through gRPC."""

from contextlib import asynccontextmanager
import grpc
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from math import inf, isfinite

from agent.algorithms.grid_search import _score, graph_from_weights, grid_search
from agent.algorithms.main_algo_1 import main_algo_1
from agent.algorithms.random_search import random_search
from agent.environment_client import EnvironmentClient
from agent.registry import ALGORITHMS
from agent.runner import Runner, RunnerError

HEURISTICS = ('zero', 'l1', 'l2', 'squared_l2', 'mse', 'linf')


class RunConfiguration(BaseModel):
    algorithm: str = 'astar'
    heuristic: str = 'l1'
    w: float = Field(default=1.0, ge=1)
    interval_ms: int = Field(default=300, ge=50, le=5000, strict=True)
    max_turns: int = Field(default=1000, ge=1, le=10000, strict=True)


class GridPoint(BaseModel):
    x: int = Field(strict=True)
    y: int = Field(strict=True)


class GridSearchConfiguration(BaseModel):
    heuristic: str = 'l1'
    low: float = Field(default=1, ge=1)
    high: float = Field(default=10, ge=1)
    step: float = Field(default=1, gt=0)
    start: GridPoint
    goal: GridPoint
    weights: list[list[float | None]] = Field(min_length=1, max_length=40)


class RandomSearchConfiguration(BaseModel):
    heuristic: str = 'l1'
    low: float = Field(default=1, ge=1)
    high: float = Field(default=50, ge=1)
    count: int = Field(default=10, ge=1, le=200, strict=True)
    start: GridPoint
    goal: GridPoint
    weights: list[list[float | None]] = Field(min_length=1, max_length=40)


class MainAlgoConfiguration(BaseModel):
    heuristic: str = 'l1'
    start: GridPoint
    goal: GridPoint
    weights: list[list[float | None]] = Field(min_length=1, max_length=40)


@asynccontextmanager
async def lifespan(app):
    client = EnvironmentClient()
    app.state.runner = Runner(client)
    try:
        yield
    finally:
        await app.state.runner.pause()
        try:
            await app.state.runner.stop()
        except grpc.aio.AioRpcError:
            pass
        await client.close()


app = FastAPI(title='Student Agent', lifespan=lifespan)


@app.exception_handler(RunnerError)
async def runner_error(request, exc):
    return JSONResponse(status_code=409, content={'detail': str(exc)})


@app.exception_handler(grpc.aio.AioRpcError)
async def grpc_error(request, exc):
    status = 503 if exc.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED) else 409
    return JSONResponse(status_code=status, content={'detail': exc.details() or exc.code().name})


@app.get('/health')
async def health():
    return {'status': 'ok'}


@app.get('/algorithms')
async def algorithms():
    return [dict(id=key, label=value.label, description=value.description)
            for key, value in ALGORITHMS.items()]


@app.get('/state')
async def state(request: Request):
    async with request.app.state.runner.lock:
        return request.app.state.runner.snapshot()


@app.get('/history')
async def history(request: Request, after_sequence: int = 0, run_id: str = ''):
    runner = request.app.state.runner
    async with runner.lock:
        if run_id and (not runner.state or runner.state['run_id'] != run_id):
            raise HTTPException(409, 'Run changed; reload its history')
        return dict(run_id=runner.state['run_id'] if runner.state else None,
                    initial_knowledge=getattr(runner, 'initial_knowledge', []),
                    events=[e for e in runner.history if e['sequence'] > after_sequence][:100])


@app.post('/runs')
async def create_run(body: RunConfiguration, request: Request):
    if body.algorithm not in ALGORITHMS:
        raise HTTPException(422, 'Unknown algorithm')
    if body.heuristic not in HEURISTICS:
        raise HTTPException(422, 'Unknown heuristic')
    return await request.app.state.runner.create(body.model_dump())


def _finite(value):
    return None if value == inf or not isfinite(value) else value


def _public_trial(trial):
    return dict(w=trial['w'], cost=_finite(trial['cost']), duration=trial['duration'],
                expansions=trial['expansions'], score=_finite(trial['score']))


@app.post('/grid-search')
async def search_weights(body: GridSearchConfiguration):
    if int((body.high - body.low) / body.step + 1e-9) + 1 > 200:
        raise HTTPException(422, 'Too many values; increase the step')
    return _publish_search(body, lambda graph, start, goal: grid_search(
        graph, start, goal, body.heuristic, body.low, body.high, body.step))


@app.post('/random-search')
async def draw_weights(body: RandomSearchConfiguration):
    return _publish_search(body, lambda graph, start, goal: random_search(
        graph, start, goal, body.heuristic, body.low, body.high, body.count))


@app.post('/main-algo-1')
async def run_main_algo(body: MainAlgoConfiguration):
    if body.heuristic not in HEURISTICS:
        raise HTTPException(422, 'Unknown heuristic')
    try:
        _require_walkable(body.weights, body.start, 'Start')
        _require_walkable(body.weights, body.goal, 'Goal')
        report = main_algo_1(body.weights, (body.start.x, body.start.y), (body.goal.x, body.goal.y), body.heuristic)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    measured = [_measured(trial) for trial in report['grid']['trials']]
    for climb in report['climbs']:
        measured.extend(_measured(trial) for trial in climb['trials'])
    best_cost = min(trial['cost'] for trial in measured)
    best_duration = min(trial['duration'] for trial in measured)
    for trial in measured:
        trial['score'] = _score(trial, best_cost, best_duration)
    best = min(measured, key=lambda trial: (trial['score'], trial['w']))
    return dict(ceiling=report['ceiling'], best=_public_trial(best), trials=[_public_trial(trial) for trial in measured])


def _measured(trial):
    return dict(w=trial['w'], cost=trial['cost'], duration=trial['duration'], expansions=trial['expansions'])


def _publish_search(body, search):
    if body.heuristic not in HEURISTICS:
        raise HTTPException(422, 'Unknown heuristic')
    if body.low > body.high:
        raise HTTPException(422, 'The lower bound must not exceed the upper bound')
    try:
        _require_walkable(body.weights, body.start, 'Start')
        _require_walkable(body.weights, body.goal, 'Goal')
        report = search(graph_from_weights(body.weights), (body.start.x, body.start.y), (body.goal.x, body.goal.y))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    trials = [_public_trial(trial) for trial in report['trials']]
    best = next(trial for trial in trials if trial['w'] == report['best']['w'])
    return dict(best=best, trials=trials)


def _require_walkable(weights, point, label):
    if point.y < 0 or point.y >= len(weights) or not weights[point.y] or point.x < 0 or point.x >= len(weights[point.y]):
        raise ValueError(f'{label} is outside the map')
    if weights[point.y][point.x] is None:
        raise ValueError(f'{label} must be a walkable cell')


@app.post('/step')
async def step(request: Request):
    return await request.app.state.runner.step()


@app.post('/run')
async def run(request: Request):
    return await request.app.state.runner.run()


@app.post('/pause')
async def pause(request: Request):
    return await request.app.state.runner.pause()


@app.post('/stop')
async def stop(request: Request):
    return await request.app.state.runner.stop()
