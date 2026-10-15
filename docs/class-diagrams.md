# Class diagrams

These diagrams show the functional classes in the environment and agent. Data
transfer models, exceptions, protocols, and gRPC-generated classes are omitted.

## Environment

```mermaid
classDiagram
    direction LR

    class Grid {
        +int width
        +int height
        +Graph graph
        -dict removed_weights
        +is_walkable(node) bool
        +set_weight(node, weight)
        +set_all_weights(weight)
        +reset_weights()
        +neighbors(node) list
        +remove_node(node)
        +add_node(node)
        +create_obstacles(count) list
    }

    class Simulation {
        -Callable grid_provider
        +Lock lock
        +dict run
        +list events
        +active bool
        +scenario() dict
        +configure(start, goal) dict
        +protect_obstacle(nodes)
        +require_run(run_id)
        +observe() dict
        +state() dict
        +start_run(request_id) dict
        +apply(run_id, expected_turn, action_id, target, stop_reason) dict
        +end(run_id) dict
    }

    Simulation --> Grid : accesses through provider
```

`Grid` owns the mutable NetworkX map. `Simulation` accesses the current grid
through a provider so replacing or resizing the grid does not require replacing
the simulation instance.

## Agent

```mermaid
classDiagram
    direction LR

    class Runner {
        +Lock lock
        +dict state
        +str status
        +list history
        +RunGraph memory
        +snapshot() dict
        +create(config)
        +step(background)
        +run()
        +pause()
        +stop()
    }

    class RunGraph {
        +dict edges
        +dict weights
        +set visited
        +seed(snapshot)
        +observe(observation)
        +view() GraphView
        +snapshot() list
    }

    class Agent {
        +AgentConfig config
        +list path
        +reset(config)
        +decide(observation, knowledge) Decision
    }

    class AStar {
        +str heuristic
        +estimate(node, target) float
        +search(graph, start, target) PlanningResult
    }

    class Dijkstra {
        +estimate(node, target) float
    }

    Runner *-- RunGraph : owns frozen map and visits
    Runner --> Agent : executes decisions
    Agent o-- AStar : selected search
    AStar <|-- Dijkstra : zero estimate
```

`Runner` controls execution and records each turn. It loads `RunGraph` from the
complete frozen run grid and records physical visits from observations. `Agent`
executes the selected Dijkstra or A* search, then follows its cached route and
stops at the goal without exploration. A* receives the configured heuristic;
Dijkstra reuses the search with zero estimates.
