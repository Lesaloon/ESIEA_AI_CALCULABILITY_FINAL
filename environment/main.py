"""Bootstrap the simulation environment."""

if __package__:
    from .grid import Grid
else:
    from grid import Grid

OBSTACLE_COUNT = 10


def main() -> None:
    grid = Grid(width=10, height=10)
    print(f"Environment initialized with a {grid.width}x{grid.height} grid")

    grid.create_obstacles(OBSTACLE_COUNT)


if __name__ == "__main__":
    main()
