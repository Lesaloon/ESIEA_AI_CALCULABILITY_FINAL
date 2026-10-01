# AI Calculability

Docker Compose scaffold for the architecture in `docs/archi.png`.

## Services

| Service | Expected build folder | Browser endpoint |
| --- | --- | --- |
| Angular control panel | `control-panel/` | `http://localhost:4200` |
| Python environment | `environment/` | `http://localhost:8000` |
| Python agent | `agent/` | `http://localhost:8001` |

All three services share the `simulation` bridge network. The agent is configured
to connect to a future environment gRPC server at `environment:50051`; this port
is not published to the host. The gRPC server is not implemented yet.
The control panel is intended to control both Python services over HTTP.

## Application requirements

Each application folder contains a Dockerfile: Nginx for the control panel
and Python slim for the environment and agent. Control-panel and agent
code and startup commands still need to be added. For now, Nginx
serves its default page. The environment initializes a NetworkX grid and starts
a FastAPI HTTP server; the agent exits without starting a service.

- Build the Angular application and copy its static output into Nginx's
  `/usr/share/nginx/html` directory. Nginx listens on port `80` inside its
  container, mapped to port `4200` on the host.
- Python services must read the HTTP/gRPC settings in `compose.yml` and bind
  their servers accordingly. These variables are an application convention,
  not settings that Docker implements automatically.
- The agent must read `ENVIRONMENT_GRPC_ADDRESS` and retry connections while
  the environment starts or restarts.
- Configure Angular's browser-side API URLs as `http://localhost:8000` and
  `http://localhost:8001`. Docker service names only resolve inside the Docker
  network, not in the user's browser. Allow the `http://localhost:4200` origin
  in both Python HTTP APIs' CORS settings.

The host ports bind to loopback for local development.

## Commands

Run the environment server locally from the project root:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r environment/requirements.txt
python -m environment.main
```

The server defaults to `http://127.0.0.1:8000`. Override its bind address and port
with `HTTP_HOST` and `HTTP_PORT`; Docker uses `0.0.0.0:8000`.

- `GET /health`: server health status.
- `GET /grid`: grid dimensions and node/edge counts.
- `GET /grid/render`: grid dimensions and a two-dimensional matrix of cell enums.
- `POST /grid/obstacles/{x}/{y}`: remove a cell and its edges to create an
  obstacle. Returns `201` with `{"x": x, "y": y}`, `404` for out-of-bounds
  coordinates, or `409` if the cell is already an obstacle.
- `/docs`: interactive Swagger UI.
- `/redoc`: alternative API documentation.

CORS allows the control panel origin `http://localhost:4200` for GET and POST requests.

For example, add an obstacle at `(3, 4)`:

```sh
curl -X POST http://localhost:8000/grid/obstacles/3/4
```

For development with automatic reload, run
`python -m uvicorn environment.main:app --reload --host 127.0.0.1 --port 8000`.

Startup creates a 10×10 `Grid`. Its `graph` attribute is a NetworkX graph
with `(x, y)` nodes and horizontal/vertical edges, without wrapping at boundaries.
Import the library with `from environment.grid import Grid` from the project root.

### Frontend grid rendering

Fetch `GET /grid/render` to get a snapshot of the current grid. For example, a
3×2 grid with an obstacle at `(1, 0)` would return:

```json
{
  "width": 3,
  "height": 2,
  "cells": [
    ["empty", "obstacle", "empty"],
    ["empty", "empty", "empty"]
  ]
}
```

Coordinates are zero-based: access a cell with `cells[y][x]`. Each of the
`height` rows contains `width` values. Cell types are string enums defined in
the OpenAPI schema: `empty` and `obstacle`.

The API uses the shared renderer, with missing NetworkX nodes rendered as
obstacles. Fetch again after adding an obstacle to get the updated matrix.

```ts
type CellType = 'empty' | 'obstacle';
interface GridRender {
  width: number;
  height: number;
  cells: CellType[][];
}
```

### Docker

Validate the Compose configuration:

```sh
docker compose config --quiet
```

Build and start the containers:

```sh
docker compose up --build
```

Stop and remove the containers:

```sh
docker compose down
```
