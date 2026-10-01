# AI Calculability

Angular + Spartan UI control panel and Python environment, following `docs/archi.png`.

## Services

| Service | Expected build folder | Browser endpoint |
| --- | --- | --- |
| Angular control panel | `control-panel/` | `http://localhost:4200` |
| Python environment | `environment/` | `http://localhost:4200/api/environment/health` (Docker proxy) |
| Python agent | `agent/` | `http://localhost:8001` |

All three services share the `simulation` bridge network. The agent connects to
the environment gRPC server at `environment:50051`; this port is not published
to the host. The control panel controls both services over proxied HTTP.
See [the student agent guide](docs/agent.md) for extension interfaces, turn
semantics, distance metrics, and the A*/Dijkstra exercises.

## Application requirements

Each application folder contains a Dockerfile: Node builds the Angular panel,
Nginx serves it, and Python slim runs the environment and agent. Both Python
images use the repository-root build context to include shared protobuf
contracts. The environment owns the NetworkX grid and serves HTTP + gRPC;
the agent serves HTTP controls and executes student policies over gRPC.

- The control-panel Dockerfile builds Angular and copies the static output into
  Nginx's `/usr/share/nginx/html` directory. Port `80` inside the container is
  mapped to port `4200` on the host.
- Python services must read the HTTP/gRPC settings in `compose.yml` and bind
  their servers accordingly. These variables are an application convention,
  not settings that Docker implements automatically.
- The agent must read `ENVIRONMENT_GRPC_ADDRESS` and retry connections while
  the environment starts or restarts.
- `/api/agent` proxies to `agent:8001` in Docker and `127.0.0.1:8001` locally.
- The panel uses the relative API URL `/api/environment`. In Docker, Nginx
  forwards it to `environment:8000` on the internal network. The environment's
  port 8000 is not published, avoiding conflicts with other local servers.
  During local development, Angular's `proxy.conf.json` forwards that same URL
  to `127.0.0.1:8000`. Environment CORS also permits direct local development
  requests from `http://localhost:4200` and `http://127.0.0.1:4200`.

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
- `GET /grid/render`: grid dimensions, cell enums, and node weights as row-major matrices.
- `POST /grid/obstacles/{x}/{y}`: remove a cell and its edges to create an
  obstacle. Returns `201` with `{"x": x, "y": y}`, `404` for out-of-bounds
  coordinates, or `409` if the cell is already an obstacle.
- `DELETE /grid/obstacles/{x}/{y}`: restore a node, its previous weight, and
  connections to adjacent walkable nodes. Returns `200` with `{"x": x, "y": y}`,
  `404` for out-of-bounds coordinates, or `409` if the cell is already empty.
- `POST /grid/obstacles/stroke`: accept `{"obstacle": true, "cells": [{"x": 0, "y": 1}]}`
  to paint obstacles, or `"obstacle": false` to erase them. Updates 1–400 cells
  atomically and returns the updated grid render. Cells already in the requested
  state are unchanged. Invalid coordinates return `404` without partial updates;
  invalid payloads return `422`. Erasing restores saved weights and connections.
- `POST /grid/reset`: clear all obstacles, preserving the dimensions, and return
  the updated grid render with weights reset to 1. State is in memory and also resets on server restart.
- `POST /grid/weights/{x}/{y}`: accept `{"weight": 3}` to update one walkable
  cell. Returns the updated grid render, `404` outside the grid, or `409` for an obstacle.
- `POST /grid/weights`: accept `{"weight": 3}` to update all walkable cells,
  preserving obstacles and their saved weights. Returns the updated grid render.
- `POST /grid/weights/stroke`: accept `{"weight": 3, "cells": [{"x": 0, "y": 1}]}`
  to paint 1–400 cells atomically. Validates the whole stroke before changing
  anything; returns `404` for out-of-bounds coordinates or `409` for obstacles.
- `POST /grid/weights/reset`: reset all weights to 1, including saved weights
  beneath obstacles, without removing obstacles. Returns the updated grid render.
  Weight edits require integers from 1 through 9; invalid values return `422`.
- `POST /grid/resize`: accept `{"size": 3}` through `{"size": 20}` and return a
  fresh square grid. Clears obstacles and resets weights to 1. Non-integer or
  out-of-range sizes return `422` without changing the current grid.
- `/docs`: interactive Swagger UI.
- `/redoc`: alternative API documentation.

The FastAPI app, routes, and lifespan live in `environment/api.py`.
`environment/main.py` only starts Uvicorn using the configured host and port.

For example, add an obstacle at `(3, 4)`:

```sh
curl -X POST http://localhost:8000/grid/obstacles/3/4
```

Remove it again with `curl -X DELETE http://localhost:8000/grid/obstacles/3/4`.
In Docker, use `http://localhost:4200/api/environment` instead of
`http://localhost:8000` for these requests.

For development with automatic reload, run
`python -m uvicorn environment.api:app --reload --host 127.0.0.1 --port 8000`.

Startup creates a 10×10 `Grid`. Its `graph` attribute is a NetworkX graph
with `(x, y)` nodes and horizontal/vertical edges, without wrapping at boundaries.
Each node has a `weight` attribute defaulting to `1`. Blocking and restoring a
node preserves its weight; clearing the grid creates fresh nodes with weight `1`.
Import the library with `from environment.grid import Grid` from the project root.

### Frontend grid rendering

Start the Angular panel in a second terminal (Node.js 24.15+ LTS recommended):

```sh
cd control-panel
npm ci
npm start
```

Open `http://localhost:4200`. The **Environment** tab contains the grid editor
and configurable start/goal placement. The **Agent** tab contains algorithm
selection, Step/Run/Pause/Reset controls, local observations, distance metrics,
movement history and replay. Start the agent locally with `python -m agent.main`
after installing `agent/requirements.txt`. Switching tabs preserves shared state.
Use Left/Right arrows or Home/End to navigate the tabs with a keyboard.

In **Obstacles** mode, hold the left mouse button
and drag: start on an empty cell to paint obstacles, or on an obstacle to erase.
The initial action stays fixed throughout the stroke, including when retracing
cells. Changes preview immediately and save together on release, even outside
the grid. Erased cells show `…` until their saved weights are restored by the server.
Single clicks and keyboard activation also toggle obstacles. The number inside each walkable cell is its node
weight (distinct from the edge weights in the separate `weights.py` utility).
Use the **Grid size** slider (3×3–20×20), then **Apply size** to create a fresh
grid. The slider previews the size; the grid changes only when applied.
Switch **Edit mode** to **Weights**, select an integer from 1–9 with the slider
or number input, then hold the left mouse button and drag across walkable cells.
The brush previews weights immediately, fills gaps during fast drags, and saves
the whole stroke when released (including outside the grid). Obstacles are skipped.
Failed saves restore the previous display and show an error; refresh to confirm
server state. Single clicks, touch taps, and Tab followed by Enter/Space also work. The blue
shading increases with weight; numbers remain visible. Obstacles cannot be
edited in this mode. **Apply to all walkable cells** sets the selected weight
across the walkable grid, retaining saved weights beneath obstacles.
**Reset weights** resets visible and saved weights to 1 without removing obstacles.
Coordinates are displayed along the top and left edges. **Reset grid** removes
all obstacles and resets weights to 1; **Refresh** reloads the environment state. There is no random
obstacle placement in the panel. Requests show loading/error feedback and the
grid can also be operated with Tab and Enter/Space.

Build for production with `npm run build` from `control-panel/`.
Spartan Helm button sources are under `control-panel/src/app/ui/`, generated
with the Spartan CLI; the panel uses Angular signals and built-in control flow.
The root component contains the workspace tabs. Feature components live in
`src/app/environment/` (panel, grid controls, and grid rendering) and
`src/app/agent/` (execution and replay). `EnvironmentStore` owns the environment
state, brush operations, and API calls. `SimulationStore` shares scenario/run
state across tabs; `SimulationGrid` renders both editor and history overlays.

Fetch `GET /grid/render` to get a snapshot of the current grid. For example, a
3×2 grid with an obstacle at `(1, 0)` would return:

```json
{
  "width": 3,
  "height": 2,
  "cells": [
    ["empty", "obstacle", "empty"],
    ["empty", "empty", "empty"]
  ],
  "weights": [
    [1, null, 1],
    [1, 1, 1]
  ]
}
```

Coordinates are zero-based: access a cell with `cells[y][x]`. Each of the
`height` rows contains `width` values. Cell types are string enums defined in
the OpenAPI schema: `empty` and `obstacle`.
Access node weights with `weights[y][x]`; obstacles have `null` weight.

The API uses the shared renderer, with missing NetworkX nodes rendered as
obstacles. Fetch again after adding an obstacle to get the updated matrix.

```ts
type CellType = 'empty' | 'obstacle';
interface GridRender {
  width: number;
  height: number;
  cells: CellType[][];
  weights: (number | null)[][];
}
```

Run graph restoration tests with `python -m unittest environment.test_grid -v`.
For weight API tests, install `python -m pip install -r environment/requirements-dev.txt`,
then run `python -m unittest environment.test_grid environment.test_api -v`.

### Docker

Validate the Compose configuration:

```sh
docker compose config --quiet
```

Build and start the containers:

```sh
docker compose up -d --build
```

Open **http://localhost:4200** (HTTP). The panel waits for the environment and
agent health checks before starting. Subsequent starts can use `docker compose up -d`;
after changing application code, use `--build` to update the images.
Check the proxied API with `curl http://localhost:4200/api/environment/grid/render`.

Stop and remove the containers:

```sh
docker compose down
```
