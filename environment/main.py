"""Bootstrap the simulation environment."""

if __package__:
    from .grid import Grid
else:
    from grid import Grid


def main() -> None:
    grid = Grid(width=10, height=10)
    print(f"Environment initialized with a {grid.width}x{grid.height} grid")


if __name__ == "__main__":
    main()
