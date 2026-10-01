"""FastAPI server for the simulation environment."""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

if __package__:
    from .grid import Grid
else:
    from grid import Grid

OBSTACLE_COUNT = 10


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
