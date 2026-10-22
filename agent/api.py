"""Browser-facing controls; all environment access goes through gRPC."""

import asyncio
from contextlib import asynccontextmanager
from typing import Literal
import grpc
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from agent import experiments
from agent.environment_client import EnvironmentClient
from agent.registry import ALGORITHMS, OPTIMIZERS
from agent.runner import Runner, RunnerError


class RunConfiguration(BaseModel):
    algorithm: str = 'astar'
    heuristic: str = 'l1'
    weight: float = Field(default=1.0, ge=1, le=20)
    optimizer: str = 'none'
    optimizer_params: dict[str, float] = Field(default_factory=dict)
    interval_ms: int = Field(default=300, ge=50, le=5000, strict=True)
    max_turns: int = Field(default=1000, ge=1, le=10000, strict=True)


Heuristic = Literal['zero', 'l1', 'l2', 'squared_l2', 'mse', 'linf']
Obstacle = Literal['none', 'u', 'wall', 'random']


class MapSelection(BaseModel):
    """Map configurations to build: every combination of sizes, connectivities and obstacles."""
    sizes: list[int] = Field(default=[20], min_length=1, max_length=4)
    connectivities: list[Literal[4, 8]] = Field(default=[4, 8], min_length=1, max_length=2)
    obstacles: list[Obstacle] = Field(default=['none', 'u', 'wall'], min_length=1, max_length=4)
    weights: Literal['random', 'uniform'] = 'random'
    seed: int = Field(default=0, ge=0, le=1_000_000)


class BenchmarkRequest(MapSelection):
    heuristics: list[Heuristic] = Field(default=['l1', 'l2'], min_length=1, max_length=6)
    algorithms: list[Literal['dijkstra', 'astar', 'weighted_astar', 'greedy']] = Field(
        default=['dijkstra', 'astar', 'weighted_astar', 'greedy'], min_length=1, max_length=4)
    weight: float = Field(default=2.0, ge=1, le=20)
    repeat: int = Field(default=3, ge=1, le=7)


class TransferRequest(MapSelection):
    sizes: list[int] = Field(default=[10, 20, 30], min_length=1, max_length=4)
    obstacles: list[Obstacle] = Field(default=['none', 'u', 'wall', 'random'], min_length=1, max_length=4)
    heuristic: Heuristic = 'linf'
    weight: float = Field(default=2.0, ge=1, le=20)
    lock_heuristic: bool = False
    weight_min: float = Field(default=1.0, ge=1, le=20)
    weight_max: float = Field(default=5.0, ge=1, le=20)
    weight_step: float = Field(default=0.5, ge=0.1, le=5)
    cost_weight: float = Field(default=1.0, ge=0, le=10)
    time_weight: float = Field(default=1.0, ge=0, le=10)
    memory_weight: float = Field(default=1.0, ge=0, le=10)


class TuneRequest(BaseModel):
    """One generated map (the fixed configuration) and the optimizers to compare on it."""
    size: int = Field(default=20, ge=8, le=40)
    connectivity: Literal[4, 8] = 8
    obstacle: Obstacle = 'u'
    weights: Literal['random', 'uniform'] = 'random'
    seed: int = Field(default=0, ge=0, le=1_000_000)
    optimizers: list[Literal['grid', 'random', 'hill_climbing', 'simulated_annealing', 'tabu']] = Field(
        default=['grid', 'random', 'hill_climbing', 'simulated_annealing', 'tabu'], min_length=1, max_length=5)
    heuristic: Heuristic = 'l1'
    weight: float = Field(default=2.0, ge=1, le=20)
    params: dict[str, float] = Field(default_factory=dict)


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


@app.get('/optimizers')
async def optimizers():
    return [dict(id=key, label=value.label, description=value.description, uses_start=value.uses_start,
                 params=[param.__dict__ for param in value.params])
            for key, value in OPTIMIZERS.items()]


async def experiment(function, **values):
    """CPU-bound experiments run off the event loop so the simulation stays responsive."""
    if any(not 8 <= size <= 40 for size in values.get('sizes', [])):
        raise HTTPException(422, 'Map sizes must be between 8 and 40')
    try:
        return await asyncio.to_thread(function, **values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/experiments/benchmark')
async def benchmark(body: BenchmarkRequest):
    """Compare the algorithms on generated maps (time, memory, explored nodes, depth, cost)."""
    return await experiment(experiments.benchmark, **body.model_dump())


@app.post('/experiments/transfer')
async def transfer(body: TransferRequest):
    """Test a tuned (heuristic, weight) on variable configurations against other strategies."""
    values = body.model_dump()
    if values['weight_min'] > values['weight_max']:
        raise HTTPException(422, 'Weight min must not exceed weight max')
    if not any(values[k] for k in ('cost_weight', 'time_weight', 'memory_weight')):
        raise HTTPException(422, 'At least one importance must be above zero')
    return await experiment(experiments.transfer, **values)


@app.post('/experiments/tune')
async def tune(body: TuneRequest):
    """Compare the optimizers on one generated map, with the score landscape for reference."""
    return await experiment(experiments.tune, **body.model_dump())


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
    if body.heuristic not in ('zero', 'l1', 'l2', 'squared_l2', 'mse', 'linf'):
        raise HTTPException(422, 'Unknown heuristic')
    config = body.model_dump()
    if body.optimizer != 'none':
        if body.optimizer not in OPTIMIZERS:
            raise HTTPException(422, 'Unknown optimizer')
        if body.algorithm != 'astar':
            raise HTTPException(422, 'Optimizers only tune A*')
        try:
            config['optimizer_params'] = OPTIMIZERS[body.optimizer].resolve(body.optimizer_params)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    return await request.app.state.runner.create(config)


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
