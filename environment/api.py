"""FastAPI server for the simulation environment."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .simulation import Simulation, SimulationError
from .grpc_server import start_server

if __package__:
    from .grid import CellType, Grid, to_cells
else:
    from grid import CellType, Grid, to_cells


class GridRender(BaseModel):
    width: int
    height: int
    cells: list[list[CellType]] = Field(
        description="Row-major matrix: cells[y][x], with zero-based coordinates."
    )
    weights: list[list[float | None]] = Field(
        description="Node weights at weights[y][x]; null for obstacles."
    )


class GridResize(BaseModel):
    size: int = Field(ge=3, le=20, strict=True)


class GridWeight(BaseModel):
    weight: int = Field(ge=1, le=9, strict=True)


class GridCoordinate(BaseModel):
    x: int = Field(strict=True)
    y: int = Field(strict=True)


class ScenarioConfiguration(BaseModel):
    start: GridCoordinate | None = None
    goal: GridCoordinate | None = None


class GridWeightStroke(GridWeight):
    cells: list[GridCoordinate] = Field(min_length=1, max_length=400)


class GridObstacleStroke(BaseModel):
    obstacle: bool = Field(strict=True)
    cells: list[GridCoordinate] = Field(min_length=1, max_length=400)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.grid = Grid(width=10, height=10)
    app.state.simulation = Simulation(lambda: app.state.grid)
    server, app.state.grpc_port = await start_server(app.state.simulation)
    try:
        yield
    finally:
        await server.stop(0)


app = FastAPI(title="Simulation Environment", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.middleware('http')
async def synchronize_grid(request: Request, call_next):
    if request.url.path.startswith(('/grid', '/scenario', '/runs')):
        async with request.app.state.simulation.lock:
            if request.method != 'GET' and request.app.state.simulation.active:
                return JSONResponse(status_code=409, content={'detail': 'End the current run before editing its scenario'})
            return await call_next(request)
    return await call_next(request)


@app.exception_handler(SimulationError)
async def simulation_error(request, exc):
    return JSONResponse(status_code=exc.status, content={'detail': str(exc)})


@app.get('/scenario')
async def get_scenario(request: Request):
    return request.app.state.simulation.scenario()


@app.post('/scenario')
async def configure_scenario(body: ScenarioConfiguration, request: Request):
    return request.app.state.simulation.configure(
        (body.start.x, body.start.y) if body.start else None,
        (body.goal.x, body.goal.y) if body.goal else None)


@app.get('/runs/{run_id}/grid', response_model=GridRender)
async def run_grid(run_id: str, request: Request):
    """UI-only frozen map for replay; deliberately absent from the gRPC API."""
    simulation = request.app.state.simulation
    simulation.require_run(run_id)
    return simulation.run['grid_snapshot']


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/grid")
def get_grid(request: Request) -> dict[str, int]:
    grid: Grid = request.app.state.grid
    return {
        "width": grid.width,
        "height": grid.height,
        "nodes": grid.graph.number_of_nodes(),
        "edges": grid.graph.number_of_edges(),
    }


@app.get("/grid/render", response_model=GridRender)
async def render_grid(request: Request) -> GridRender:
    """Render the current grid as cell types for the frontend."""
    grid: Grid = request.app.state.grid
    weights = [
        [grid.graph.nodes[x, y]["weight"] if grid.is_walkable((x, y)) else None
         for x in range(grid.width)]
        for y in range(grid.height)
    ]
    return GridRender(width=grid.width, height=grid.height, cells=to_cells(grid), weights=weights)


@app.post("/grid/obstacles/{x}/{y}", status_code=201)
async def add_obstacle(x: int, y: int, request: Request) -> dict[str, int]:
    grid: Grid = request.app.state.grid
    request.app.state.simulation.protect_obstacle([(x, y)])
    if not (0 <= x < grid.width and 0 <= y < grid.height):
        raise HTTPException(status_code=404, detail="Coordinates are outside the grid")
    try:
        grid.remove_node((x, y))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Cell is already an obstacle") from exc
    return {"x": x, "y": y}


@app.delete("/grid/obstacles/{x}/{y}")
async def remove_obstacle(x: int, y: int, request: Request) -> dict[str, int]:
    grid: Grid = request.app.state.grid
    if not (0 <= x < grid.width and 0 <= y < grid.height):
        raise HTTPException(status_code=404, detail="Coordinates are outside the grid")
    try:
        grid.add_node((x, y))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Cell is already empty") from exc
    return {"x": x, "y": y}


@app.post("/grid/reset", response_model=GridRender)
async def reset_grid(request: Request) -> GridRender:
    grid: Grid = request.app.state.grid
    request.app.state.grid = Grid(width=grid.width, height=grid.height)
    return await render_grid(request)


@app.post("/grid/obstacles/stroke", response_model=GridRender)
async def paint_obstacles(body: GridObstacleStroke, request: Request) -> GridRender:
    """Set the desired cell state atomically, preserving saved node weights."""
    grid: Grid = request.app.state.grid
    if body.obstacle:
        request.app.state.simulation.protect_obstacle([(cell.x, cell.y) for cell in body.cells])
    for cell in body.cells:
        if not (0 <= cell.x < grid.width and 0 <= cell.y < grid.height):
            raise HTTPException(status_code=404, detail="Coordinates are outside the grid")
    for cell in body.cells:
        node = (cell.x, cell.y)
        if body.obstacle and grid.is_walkable(node):
            grid.remove_node(node)
        elif not body.obstacle and not grid.is_walkable(node):
            grid.add_node(node)
    return await render_grid(request)


@app.post("/grid/weights/{x}/{y}", response_model=GridRender)
async def set_weight(x: int, y: int, body: GridWeight, request: Request) -> GridRender:
    grid: Grid = request.app.state.grid
    if not (0 <= x < grid.width and 0 <= y < grid.height):
        raise HTTPException(status_code=404, detail="Coordinates are outside the grid")
    if not grid.is_walkable((x, y)):
        raise HTTPException(status_code=409, detail="Cannot set the weight of an obstacle")
    grid.set_weight((x, y), body.weight)
    return await render_grid(request)


@app.post("/grid/weights", response_model=GridRender)
async def set_all_weights(body: GridWeight, request: Request) -> GridRender:
    grid: Grid = request.app.state.grid
    grid.set_all_weights(body.weight)
    return await render_grid(request)


@app.post("/grid/weights/stroke", response_model=GridRender)
async def paint_weights(body: GridWeightStroke, request: Request) -> GridRender:
    """Validate the entire stroke before updating any cells."""
    grid: Grid = request.app.state.grid
    for cell in body.cells:
        if not (0 <= cell.x < grid.width and 0 <= cell.y < grid.height):
            raise HTTPException(status_code=404, detail="Coordinates are outside the grid")
        if not grid.is_walkable((cell.x, cell.y)):
            raise HTTPException(status_code=409, detail="Cannot set the weight of an obstacle")
    for cell in body.cells:
        grid.set_weight((cell.x, cell.y), body.weight)
    return await render_grid(request)


@app.post("/grid/weights/reset", response_model=GridRender)
async def reset_weights(request: Request) -> GridRender:
    grid: Grid = request.app.state.grid
    grid.reset_weights()
    return await render_grid(request)


@app.post("/grid/resize", response_model=GridRender)
async def resize_grid(body: GridResize, request: Request) -> GridRender:
    """Replace the environment with an empty square grid of the requested size."""
    request.app.state.grid = Grid(width=body.size, height=body.size)
    request.app.state.simulation.configure(None, None)
    return await render_grid(request)
