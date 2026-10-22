# Student agent laboratory

## Run the workspace

From the repository root:

```sh
docker compose up -d --build
```

Open <http://localhost:4200>. In **Environment**, edit obstacles and weights,
then place **Start** and **Goal** on walkable cells. In **Agent**, choose a
search algorithm (Dijkstra or A*) and heuristic, create a run and click **Step**. **Run** advances automatically;
**Pause** finishes the current turn. **End run** releases the scenario for
editing. **Reset run** uses the displayed settings with fresh algorithm state
and empty history. The interval and maximum turns apply to each newly created run.

Execution continues without a browser connection; refreshing recovers the run
and history. State is in memory. After an agent restart, **End run** or creating
a new run releases an orphaned environment run. After an environment restart,
end/reset the agent run and configure the new scenario.

Local development uses three terminals:

```sh
# Terminal 1, repository root
python -m pip install -r environment/requirements.txt -r agent/requirements.txt
python -m environment.main

# Terminal 2, repository root, same virtual environment
python -m agent.main

# Terminal 3
cd control-panel
npm ci
npm start
```

Environment HTTP defaults to `127.0.0.1:8000`; gRPC defaults to
`127.0.0.1:50051`. Agent HTTP defaults to `127.0.0.1:8001`. Configure the
environment with `HTTP_HOST`, `HTTP_PORT`, `GRPC_HOST`, `GRPC_PORT`; configure
the agent with `HTTP_HOST`, `HTTP_PORT`, `ENVIRONMENT_GRPC_ADDRESS`.

## Selectable full-map algorithms

`agent/algorithms/astar.py` implements A* with the selected heuristic.
`agent/algorithms/dijkstra.py` implements Dijkstra by reusing the weighted
search with a zero estimate, so its priority is accumulated cost alone.
Both are selectable through `agent/registry.py`. `agent/algorithms/agent.py`
executes the chosen search and follows its route, without an exploration policy:

1. `Runner.create()` loads the complete frozen run grid over gRPC.
2. `Agent.reset(config)` creates the selected algorithm with the supplied
   `AgentConfig.heuristic` and clears the cached path.
3. On the first decision, the selected algorithm searches from the start to the goal.
4. `Agent.decide()` follows the cached path, one neighboring move per turn.
5. At the goal it returns `Stop`; if no route exists, it stops without moving.

The agent never selects exploration waypoints or tries to visit every cell.
Search expansions inspect the known graph without physically moving the agent.
The final path is the route actually computed before movement, reused without
another search at completion. Dijkstra always uses zero estimates, regardless
of the supplied heuristic; A* uses the chosen metric.

## What the algorithm knows

Transport-independent types live in `agent/models.py`:

- `AgentConfig.heuristic`: the selected distance metric.
- `AgentConfig.algorithm`: `dijkstra` or `astar`.
- `GraphView`: a read-only graph of **all** walkable cells in the frozen run map.
  `weights` holds entry costs, `edges[source][destination]` holds directional
  movement costs, and `visited` tracks physically occupied positions only.
- `Observation.position` and `.goal`: zero-based `(x, y)` tuples.
- `.neighbors`: the current position's walkable eight-way neighbors, including
  their entry costs and geometric distances to the goal.
- `.current_cell_weight`, `.goal_distances`, `.turn`, `.goal_reached`.

Diagonal moves are allowed even when the two side cells are obstacles. All
moves cost the destination cell's weight (1–9), including diagonal moves.
Connectivity is symmetric; movement costs need not be. `RunGraph` loads the
map once; observations subsequently record visits without discovering cells.
The graph and observations are supplied by the runner, so algorithm code does
not need to import environment internals or call the HTTP grid editor.

To modify the search, edit `AStar.search()` or `Dijkstra.estimate()`; route
execution is in `Agent.decide()`.
The search returns `PlanningResult(path, trace)`, with a path including start
and goal, `[start]` when both coincide, or `[]` if no route exists. Decisions
return `Decision(Move(neighbor), explanation, trace)` or `Decision(Stop(reason))`.
Reset private state in `reset()` for each new run. Do not mutate the graph.

## Search traces and turn semantics

One turn is one decision and committed result. A move increments the turn and
charges the destination's weight; initial placement costs zero. A `Stop` records
a turn with zero travel cost. The agent stops on its next decision after entering
the goal. Start equal to goal therefore produces just one `Stop`, with no move.
An invalid action does not advance the turn and pauses with an error. The maximum
turn limit ends the run after that many committed decisions. Manual **End run**
does not add a movement event.

The first decision includes the complete search trace:

```python
SearchTrace(
    expanded=[(0, 0), (0, 1)],
    frontier=[(1, 0)],
    candidate_path=[(0, 0), (0, 1)],
    scores=[{'x': 0, 'y': 1, 'g': 2, 'h': 3, 'f': 5}],
)
```

Later moves show the remaining cached path without new search expansions.
The UI separates actual movement from search. Select a history row or use the
replay slider to inspect that turn's observation and trace. Traces describe
planning **before** the action; observations describe the committed result.
**Live** returns to the current turn. Replay never changes execution. The
environment retains a frozen map for the latest run so later edits do not
corrupt its replay.

## Distances and heuristics

For `dx = abs(x - goal.x)` and `dy = abs(y - goal.y)`:

| Key | Value |
| --- | --- |
| `zero` | `0` (Dijkstra) |
| `l1` | `dx + dy` |
| `l2` | `sqrt(dx² + dy²)` |
| `squared_l2` | `dx² + dy²` |
| `mse` | `(dx² + dy²) / 2` |
| `linf` | `max(dx, dy)` |

`agent.distances.distance(a, b, metric)` computes the heuristic without querying
the environment. A* uses `config.heuristic` to estimate distance to the
goal and orders search nodes by `f = g + h`. Dijkstra uses `h = 0` and `f = g`.
The UI disables the heuristic selector for Dijkstra and displays Zero; switching
back to A* restores the previously chosen metric.

For eight-way moves with minimum entry cost 1, L∞ is admissible and consistent.
Zero and L∞ give minimum-cost routes. L1, L2, squared L2 and MSE can overestimate,
so the usual A* optimality guarantee does not apply to those choices.

## Transport and ownership

```text
Browser -- /api/environment HTTP --> Environment (grid + run authority)
Browser -- /api/agent HTTP -------> Agent (runner + selected search algorithm)
Agent   -- simulation.v1 gRPC ----> Environment (frozen grid + observations + actions)
```

The environment runs FastAPI and `grpc.aio` on one event loop and shares a lock
across grid edits, scenario configuration and turns. Use one process/worker per
service while state is in memory. Paused runs still lock scenario edits.

gRPC exposes `StartRun`, `Observe`, `ApplyAction`, `GetRunState`, `GetRunGrid`,
`GetTurnEvents` and `EndRun`. The agent requests `GetRunGrid` for every new run.
`GetRunState` with an empty ID recovers the latest environment run; other run
requests require a matching ID. Start requests and actions have unique IDs.
Retrying the same action returns its original result; reusing its ID for
different content fails. `expected_turn` rejects stale commands. The runner
retains a pending decision when a reply is lost so the next Step recovers the
same move without another decision or search.

Agent HTTP endpoints:

- `GET /algorithms`, `/state`, `/health`.
- `POST /runs`: `algorithm` (default `astar`), `heuristic`, `interval_ms`, `max_turns`.
- `POST /step`, `/run`, `/pause`, `/stop`.
- `GET /history?run_id=...&after_sequence=...`: up to 100 new records; paginate
  using the last sequence. A mismatched run ID fails.

Environment additions:

- `GET /scenario`: `{start, goal, locked}`.
- `POST /scenario`: `{start: {x,y} | null, goal: {x,y} | null}`.
- `GET /runs/{run_id}/grid`: frozen full-map snapshot for UI replay.

Resizing clears endpoints; resetting the grid preserves valid endpoints.
Obstacle strokes touching either endpoint fail atomically. Active runs reject
all grid/scenario writes, including while paused. Finishing, stopping or reaching
the turn limit unlocks the scenario.

## Regenerate the shared protocol

The versioned `simulation.v1` contract is in `contracts/simulation.proto`.
Generated Python modules are checked in. After modifying the proto:

```sh
python -m pip install -r contracts/requirements-dev.txt
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. contracts/simulation.proto
```

Rebuild both Python service images after protocol changes. Their build context
is the repository root so each includes the same `contracts/` package.

## Verification

```sh
python -m pip install -r environment/requirements-dev.txt
python -m unittest environment.test_grid environment.test_api environment.test_simulation -v
docker compose config --quiet
```

Run `npm run build` inside `control-panel/`. Integration tests use ephemeral
gRPC listeners and in-process HTTP clients. They cover the frozen graph,
directional costs, algorithm selection, heuristic reset, weighted detours, a single cached search,
stopping at the goal without exploration, start equal to goal, unreachable
goals, invalid/stale moves, retries, locking, replay and execution controls.

## Weighted A* and parameter optimizers

**Weighted A*** orders the frontier by `f = g + w·h` (`AStar(heuristic, weight)` in
`agent/algorithms/astar.py`). `w = 1` is classic A*. A larger `w` trusts the heuristic
more: fewer expanded nodes, less time and memory, but with an admissible heuristic (L∞)
the route may cost up to `w` times the optimum. Dijkstra ignores `w`.

**Optimizers** (`agent/algorithms/optimizers.py`) search for the best
`(heuristic, w)` pair before the first move, by running A* on the known map (no physical
move). Each trial is scored on three criteria, each divided by the same measure for the
reference search (classic A*, L∞, `w = 1`):

```text
score = cost_weight * cost/cost_ref + time_weight * time/time_ref + memory_weight * memory/memory_ref
```

`cost` is the route cost, `time` the median of 5 search durations, `memory` the peak
allocation of one search (`tracemalloc`). The three importances are editable in the UI;
set one to 0 to ignore a criterion. Time depends on the machine and is slightly noisy. Every optimizer also has `lock_heuristic` (0 by default, a checkbox in the UI): at 1 it keeps the heuristic selected in the run configuration and tunes only the weight.

| Id | Optimizer | Parameters (besides the three importances) |
| --- | --- | --- |
| `grid` | Tries every heuristic × every weight between min and max | `weight_min`, `weight_max`, `weight_step` |
| `random` | Samples random pairs, keeps the best | `trials`, `weight_min`, `weight_max`, `seed` |
| `hill_climbing` | Starts at the chosen heuristic/weight, moves to the best neighbor (`w ± step`, or another heuristic) until none improves | `weight_min`, `weight_max`, `step`, `max_iterations` |

`GET /optimizers` lists them with their parameters; the UI builds its form from that
list. `POST /runs` accepts `weight`, `optimizer` (`none` by default) and
`optimizer_params` (defaults filled in, invalid values give `422`). Optimizers only tune
A*. The first decision's trace carries `tuning`: chosen heuristic/weight, the best trial,
the reference and every trial. The **Agent** tab shows it under the grid.

To add an optimizer, subclass `Optimizer` (declare `params`, implement `optimize()`
using the `evaluate(heuristic, weight)` callable) and register it in `agent/registry.py`.

## Saved experiments

The **Experiments** tab keeps the result of optimizer runs in the browser (`localStorage`, key
`aic.saved-experiments.v1`). **Save current run** stores the first decision's `tuning` report of the
current run: best (heuristic, weight), score, search parameters, the three importances and every trial.
Runs are grouped by grid (cells, weights, start and goal, fingerprinted together; renameable), then by
scoring function (the three importances). **Load** puts a run's optimizer settings back in the Agent
tab form; it does not restore the grid. **Export CSV** writes one row per trial of every saved run.
