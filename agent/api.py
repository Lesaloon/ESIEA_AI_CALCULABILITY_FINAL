"""Browser-facing controls; all environment access goes through gRPC."""

import asyncio
from contextlib import asynccontextmanager
from typing import Literal
import grpc
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from agent.environment_client import EnvironmentClient
from agent.registry import ALGORITHMS
from agent.runner import Runner, RunnerError
from agent.tuning import Settings, map_grid_search, run_tuning


class RunConfiguration(BaseModel):
    algorithm: str = 'astar'
    heuristic: str = 'l1'
    weight: float = Field(default=2.0, ge=1, le=100)
    interval_ms: int = Field(default=300, ge=50, le=5000, strict=True)
    max_turns: int = Field(default=1000, ge=1, le=10000, strict=True)


class Point(BaseModel):
    x: int
    y: int


class MapTuningRequest(BaseModel):
    """The editor's grid (as returned by /grid/render) and scenario endpoints."""
    cells: list[list[Literal['empty', 'obstacle']]] = Field(min_length=1, max_length=40)
    weights: list[list[float | None]] = Field(min_length=1, max_length=40)
    start: Point
    goal: Point
    heuristic: Literal['zero', 'l1', 'l2', 'squared_l2', 'mse', 'linf'] = 'l1'
    w_max: int = Field(default=20, ge=2, le=100)
    alpha: float = Field(default=1.0, ge=0, le=10)
    beta: float = Field(default=1.0, ge=0, le=10)
    gamma: float = Field(default=1.0, ge=0, le=10)


class TuningRequest(BaseModel):
    """Bounds keep one tuning request well under the proxy's 20 s read timeout."""
    size: int = Field(default=30, ge=10, le=40)
    connectivity: Literal[4, 8] = 8
    heuristic: Literal['l1', 'l2', 'linf'] = 'l1'
    alpha: float = Field(default=1.0, ge=0, le=10)
    beta: float = Field(default=1.0, ge=0, le=10)
    gamma: float = Field(default=1.0, ge=0, le=10)
    max_cost_ratio: float | None = Field(default=None, ge=1, le=10)
    w_max: float = Field(default=50.0, ge=2, le=100)
    start: float = Field(default=2.4, ge=1, le=100)
    repeat: int = Field(default=3, ge=1, le=5)
    seed: int = Field(default=0, ge=0, le=1000)


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
    if body.heuristic not in ('zero', 'l1', 'l2', 'squared_l2', 'mse', 'linf'):
        raise HTTPException(422, 'Unknown heuristic')
    return await request.app.state.runner.create(body.model_dump())


@app.post('/tuning')
async def tuning(body: TuningRequest):
    if body.start > body.w_max:
        raise HTTPException(422, 'start must not exceed w_max')
    # CPU-bound: run off the event loop so the simulation endpoints stay responsive.
    return await asyncio.to_thread(run_tuning, Settings(**body.model_dump()))


@app.post('/tuning/map')
async def tuning_map(body: MapTuningRequest):
    cells = {(x, y): body.weights[y][x] or 1
             for y, row in enumerate(body.cells) for x, cell in enumerate(row) if cell == 'empty'}
    # Repeated timings: searches on editor-sized maps take only microseconds.
    settings = Settings(heuristic=body.heuristic, alpha=body.alpha, beta=body.beta, gamma=body.gamma,
                        w_max=body.w_max, repeat=7)
    try:
        return await asyncio.to_thread(map_grid_search, cells, (body.start.x, body.start.y),
                                       (body.goal.x, body.goal.y), settings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


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
