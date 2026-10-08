# Student agent laboratory

## Run the workspace

From the repository root:

```sh
docker compose up -d --build
```

Open <http://localhost:4200>. In **Environment**, edit obstacles/weights, then
place **Start** and **Goal** on walkable cells (or set their coordinates). In
**Agent**, choose **Example explorer · breadth-first**, create a run and click
**Step**. **Run** advances automatically; **Pause** finishes the current turn.
**End run** releases the scenario for editing. **Reset run** starts again at
the configured start with fresh algorithm state and empty history. It uses
the settings currently shown in the panel.

The interval and maximum turn count apply to each newly created run. A browser
refresh recovers the current run and history. Execution continues without a
browser connection. The first version stores the latest run in service memory;
service restarts clear their respective state. After an agent restart, **End
run** or creating a new run can release an orphaned environment run. After an
environment restart, end/reset the agent run and configure the new scenario.

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

## What the algorithm knows

The framework passes transport-independent types from `agent/models.py`:

- `Observation.position` and `.goal`: zero-based `(x, y)` tuples.
- `.neighbors`: **only the current position's walkable four-way neighbors**.
  Each contains its position, cost to enter, and geometric distances to the goal.
- `.current_cell_weight`, `.goal_distances`, `.turn`, `.goal_reached`.
- `DiscoveredGraphView`: a read-only graph built entirely from past observations.
  `weights` includes seen walkable cells; `visited` includes positions physically
  occupied; `edges[source][destination]` contains observed/inferred movement costs.

By default there is no arbitrary-coordinate inspection. Missing neighbors indicate
unavailable directions. Cells seen as neighbors are discovered but not fully
inspected until occupied. Known adjacent connectivity is symmetric; entering-cell
costs are directional. Never treat a missing edge between two unvisited cells as
proof that it is blocked.

Algorithms should use these types, not import environment internals or call the
teacher's HTTP grid editor. The run configuration's `full_knowledge` option seeds
the same graph view from the frozen run grid for controlled heuristic experiments.

## Exercise 1: Dijkstra or A*

Implement `DijkstraPlanner.plan` or `AStarPlanner.plan` in
`agent/planners/template.py`. The contract is:

```python
def plan(self, graph: DiscoveredGraphView,
         start: Position, target: Position) -> PlanningResult:
    ...
```

Return a list of coordinates **including start and target**, or an empty list
when there is no known route. Start equal to target should return `[start]`.
Use the actual directional costs in `graph.edges`. A successful planner does
not mutate the supplied graph.

Enable the matching entry in `agent/registry.py` by changing `enabled=False`
to `enabled=True`. Restart/rebuild the agent and refresh the browser. The
algorithm becomes selectable. Keep factory creation per run so private state
does not leak between runs.

The supplied `Explorer` policy selects a seen, unvisited cell closest to the
goal using the configured geometric metric, invokes your planner on the
discovered graph, then executes **only the first move**. It replans after each
new local observation. Once the goal is discovered, it routes toward the goal.
The supplied breadth-first planner gives a working example, but intentionally
ignores weights: it finds shortest-hop paths rather than minimum-cost paths.

Without `full_knowledge`, this is **physical exploration with replanning**, not
full-map search. Dijkstra and admissible A* find shortest routes on the graph
currently known. That graph may omit shortcuts, and exploration adds travel. Do
not claim that total travel or the first discovered goal route is globally optimal.

### Suggested planner checks

Use small directed graphs to verify:

1. A costly direct route versus a cheaper multi-hop detour.
2. Different forward and reverse costs.
3. Start equals target and an unreachable target.
4. Improving the cost of an already-discovered node.
5. Deterministic tie-breaking and path reconstruction.
6. Dijkstra and A* with zero heuristic agree on minimum cost.

For oracle comparisons, build a `networkx.DiGraph` from the supplied edges and
compare path cost with `networkx.shortest_path_length(..., weight='weight')`.
Do not require the same path when several equal-cost solutions exist.

## Exercise 2: an exploration policy

Implement `AlgoPolicy` in `agent/algorithms/algo_template.py`:

```python
def reset(self, config: AgentConfig) -> None:
    # Reset private state once per run.
    ...

def decide(self, observation: Observation,
           knowledge: DiscoveredGraphView) -> Decision:
    return Decision(
        action=Move(observation.neighbors[0].position),
        explanation='Why I chose this neighboring cell',
    )
```

Handle empty neighbor lists. Return `Stop('reason')` when finished or unable
to continue. Moves must target a current neighbor; jumping to a search node or
returning an entire path is invalid. Revisits are allowed and cost money again.
Enable the `template` entry in the registry, or register another policy factory.

## Search traces and turn semantics

One turn is one decision and one committed result. A move increments the turn
and charges the destination's weight (1–9); initial placement costs zero. A
student `Stop` also records a turn with zero travel cost. An invalid action does
not advance the turn or change the environment and pauses with an error.
Starting at the goal completes immediately at turn zero. The maximum-turn limit
ends the run after that many committed decisions. Manual **End run** is an
execution control, not an algorithm decision, and does not add a movement event.

Populate `SearchTrace` if desired:

```python
SearchTrace(
    expanded=[(0, 0), (0, 1)],
    frontier=[(1, 0)],
    candidate_path=[(0, 0), (0, 1)],
    scores=[{'x': 0, 'y': 1, 'g': 2, 'h': 3, 'f': 5}],
)
```

Search expansions happen inside a decision and do not move the agent. The UI
shows actual movement separately, including revisit counts. Select a history
row or scrub the replay slider to inspect that turn's resulting observation,
knowledge, and decision trace. Trace values describe planning **before** the
action; the accompanying observation describes the committed result. **Live**
returns to the current turn. Replay never changes live execution.

The environment retains a frozen map for the latest run via its UI-only HTTP
endpoint, so subsequent grid edits do not corrupt that run's replay.

## Distances and heuristics

For `dx = abs(x - goal.x)` and `dy = abs(y - goal.y)`:

| Key | Value |
| --- | --- |
| `zero` (planner helper only) | `0` |
| `l1` | `dx + dy` |
| `l2` | `sqrt(dx² + dy²)` |
| `squared_l2` | `dx² + dy²` |
| `mse` | `(dx² + dy²) / 2` |
| `linf` | `max(dx, dy)` |

`agent.distances.distance(a, b, metric)` works for any known coordinates and
does not access the environment. In a planner, compute the heuristic to that
planner's **target**, which may be an exploration waypoint instead of the goal.

For four-way moves with minimum entry cost 1, L1, L2 and L∞ are admissible and
consistent lower bounds. `zero` gives Dijkstra's priority. Squared L2 and MSE
can overestimate; the usual A* optimality guarantee does not apply. None of
these measurements accounts for unseen obstacles or weights.

## Transport and ownership

```text
Browser -- /api/environment HTTP --> Environment (grid + run authority)
Browser -- /api/agent HTTP -------> Agent (runner + student policies)
Agent   -- simulation.v1 gRPC ----> Environment (observations + actions + opt-in grid)
```

The environment runs FastAPI and `grpc.aio` on one event loop and shares a lock
across grid edits, scenario configuration and turns. Use one process/worker per
service while their state is in memory. Paused runs still lock scenario edits.

gRPC exposes `StartRun`, `Observe`, `ApplyAction`, `GetRunState`, `GetRunGrid`,
`GetTurnEvents` and `EndRun`. `GetRunGrid` returns the frozen snapshot for the
matching run and is requested only when `full_knowledge` is enabled. `GetRunState`
with an empty run ID recovers the latest environment run after an agent restart.
All other run requests require the matching ID.
Start requests and actions have unique request/action IDs. Retrying the same
action returns its original result; reusing its ID for different content fails.
`expected_turn` rejects stale commands. The agent retains a pending decision
when a movement reply is lost, so the next Step can recover that same move.

Agent HTTP endpoints:

- `GET /algorithms`, `/state`, `/health`.
- `POST /runs`: `algorithm`, `heuristic`, `full_knowledge`, `interval_ms`, `max_turns`.
- `POST /step`, `/run`, `/pause`, `/stop`.
- `GET /history?run_id=...&after_sequence=...`: up to 100 new records;
  retrieve additional pages using the last sequence. A mismatched run ID fails.

Environment additions:

- `GET /scenario`: `{start, goal, locked}`.
- `POST /scenario`: `{start: {x,y} | null, goal: {x,y} | null}`.
- `GET /runs/{run_id}/grid`: frozen full-map snapshot for UI replay.

Resizing clears both endpoints; resetting the grid preserves valid endpoints.
Obstacle strokes touching either endpoint fail atomically. Active runs reject
all grid/scenario writes, including while paused. Finishing, stopping or reaching
the turn limit unlocks the scenario.

## Regenerate the shared protocol

The versioned `simulation.v1` contract is in `contracts/simulation.proto`.
Generated Python modules are checked in so runtime installs do not need a compiler.
After modifying the proto, run from the repository root:

```sh
python -m pip install -r contracts/requirements-dev.txt
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. contracts/simulation.proto
```

Rebuild both Python service images after protocol changes. Their Docker build
context is the repository root so each includes the same `contracts/` package.

## Verification

```sh
python -m pip install -r environment/requirements-dev.txt
python -m unittest environment.test_grid environment.test_api environment.test_simulation -v
docker compose config --quiet
```

Run `npm run build` inside `control-panel/`. The integration tests use real
ephemeral gRPC listeners and in-process HTTP clients; no running containers are
required. They cover local visibility, directional costs, invalid/stale moves,
duplicate actions, lost replies, scenario locking, history, replay snapshots,
pause/resume, run reset, unreachable goals and turn limits.
