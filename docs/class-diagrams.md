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
        +DiscoveredGraph memory
        +snapshot() dict
        +plan_final_path() list
        +create(config)
        +step(background)
        +run()
        +pause()
        +stop()
    }

    class DiscoveredGraph {
        +dict edges
        +dict weights
        +set visited
        +observe(observation)
        +view() DiscoveredGraphView
        +snapshot() list
    }

    class Explorer {
        +planner
        +reset(config)
        +final_path(start, goal, knowledge) list
        +decide(observation, knowledge) Decision
    }

    class BreadthFirstPlanner {
        +plan(graph, start, target) PlanningResult
    }

    class DijkstraPlanner {
        +plan(graph, start, target) PlanningResult
    }

    class AStarPlanner {
        +str heuristic
        +plan(graph, start, target) PlanningResult
    }

    Runner *-- DiscoveredGraph : owns discovered knowledge
    Runner --> Explorer : executes selected policy
    Explorer o-- BreadthFirstPlanner : uses
    Explorer o-- DijkstraPlanner : uses
    Explorer o-- AStarPlanner : uses
```

`Runner` controls execution and records each turn. It updates
`DiscoveredGraph` from local observations, while `Explorer` selects a target and
delegates route calculation to the planner configured for the run.
