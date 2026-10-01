"""FastAPI server for the simulation environment."""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

if __package__:
    from .grid import CellType, Grid, to_cells
else:
    from grid import CellType, Grid, to_cells

OBSTACLE_COUNT = 10


class GridRender(BaseModel):
    width: int
    height: int
    cells: list[list[CellType]] = Field(
        description="Row-major matrix: cells[y][x], with zero-based coordinates."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.grid = Grid(width=10, height=10)
    yield


app = FastAPI(title="Simulation Environment", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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
    return GridRender(width=grid.width, height=grid.height, cells=to_cells(grid))


@app.post("/grid/obstacles/{x}/{y}", status_code=201)
async def add_obstacle(x: int, y: int, request: Request) -> dict[str, int]:
    grid: Grid = request.app.state.grid
    if not (0 <= x < grid.width and 0 <= y < grid.height):
        raise HTTPException(status_code=404, detail="Coordinates are outside the grid")
    try:
        grid.remove_node((x, y))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Cell is already an obstacle") from exc
    return {"x": x, "y": y}


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("HTTP_HOST", "127.0.0.1"),
        port=int(os.getenv("HTTP_PORT", "8000")),
    )

    grid.create_obstacles(OBSTACLE_COUNT)


if __name__ == "__main__":
    main()
