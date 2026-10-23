"""Browser-facing controls; all environment access goes through gRPC."""

from contextlib import asynccontextmanager
import grpc
import csv
import io
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from agent.environment_client import EnvironmentClient
from agent.registry import ALGORITHMS
from agent.runner import Runner, RunnerError
from agent.experiments import ExperimentConfiguration, ExperimentManager, ScoreWeights


class RunConfiguration(BaseModel):
    algorithm: str = 'astar'
    heuristic: str = 'l1'
    heuristic_weight: float = Field(default=1, ge=0, le=1000, allow_inf_nan=False)
    interval_ms: int = Field(default=300, ge=50, le=5000, strict=True)
    max_turns: int = Field(default=1000, ge=1, le=10000, strict=True)


@asynccontextmanager
async def lifespan(app):
    client = EnvironmentClient()
    app.state.runner = Runner(client)
    app.state.experiments = ExperimentManager()
    try:
        yield
    finally:
        await app.state.experiments.cancel()
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


@app.get('/experiments')
async def experiment_state(request: Request):
    return request.app.state.experiments.snapshot()


@app.post('/experiments')
async def start_experiment(body: ExperimentConfiguration, request: Request):
    try:
        return await request.app.state.experiments.start(body, request.app.state.runner.client)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post('/experiments/cancel')
async def cancel_experiment(request: Request):
    return await request.app.state.experiments.cancel()


@app.post('/experiments/scoring')
async def score_experiment(body: ScoreWeights, request: Request):
    try:
        return request.app.state.experiments.rescore(body)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get('/experiments/export')
async def export_experiment(request: Request, format: str = 'json'):
    job = request.app.state.experiments.snapshot(details=True)
    if job is None:
        raise HTTPException(404, 'No experiment available')
    headers = {'Content-Disposition': f'attachment; filename="experiment-{job["id"]}.{format}"'}
    if format == 'json':
        return JSONResponse(job, headers=headers)
    if format != 'csv':
        raise HTTPException(422, 'Use json or csv')
    output = io.StringIO()
    fields = ['method', 'trial', 'algorithm', 'heuristic', 'heuristic_weight', 'map_index',
              'success', 'cost', 'length', 'expanded', 'time_ms', 'memory_kib', 'gap_percent',
              'score_time', 'score_memory', 'score_quality', 'score_expanded', 'score', 'benchmark_ms', 'worker_pid',
              'time_mean_raw_ms', 'time_samples_ms', 'time_used_samples_ms', 'time_outlier_indices',
              'time_std_ms', 'time_min_ms', 'time_max_ms', 'timing_runs', 'timing_outliers']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(job['evaluations'])
    return Response(output.getvalue(), media_type='text/csv', headers=headers)
