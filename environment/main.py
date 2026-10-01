"""FastAPI server for the simulation environment."""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

if __package__:
    from .grid import Grid
else:
    from grid import Grid


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.grid = Grid(width=10, height=10)
    yield


app = FastAPI(title="Simulation Environment", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["GET"],
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


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("HTTP_HOST", "127.0.0.1"),
        port=int(os.getenv("HTTP_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
