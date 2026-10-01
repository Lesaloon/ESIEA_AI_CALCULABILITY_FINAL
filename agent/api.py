"""Browser-facing controls; all environment access goes through gRPC."""

from contextlib import asynccontextmanager
import grpc
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from agent.environment_client import EnvironmentClient
from agent.registry import ALGORITHMS
from agent.runner import Runner, RunnerError


class RunConfiguration(BaseModel):
    algorithm: str = 'example'
    heuristic: str = 'l1'
    interval_ms: int = Field(default=300, ge=50, le=5000, strict=True)
    max_turns: int = Field(default=1000, ge=1, le=10000, strict=True)


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
    return [dict(id=key, label=a.label, description=a.description, enabled=a.enabled)
            for key, a in ALGORITHMS.items()]


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
    if body.algorithm not in ALGORITHMS or not ALGORITHMS[body.algorithm].enabled:
        raise HTTPException(422, 'Choose an enabled algorithm in agent/registry.py')
    if body.heuristic not in ('zero', 'l1', 'l2', 'squared_l2', 'mse', 'linf'):
        raise HTTPException(422, 'Unknown heuristic')
    return await request.app.state.runner.create(body.model_dump())


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
