"""Print a grid in the terminal.

From the project root: python -m environment.grid --width 20 --height 10 --obstacles 30
"""

import argparse
import random

from .grid import Grid
from .render import format_chars, to_chars


def main() -> None:
    parser = argparse.ArgumentParser(description="Display a simulation grid in the terminal.")
    parser.add_argument("--width", type=int, default=10)
    parser.add_argument("--height", type=int, default=10)
    parser.add_argument("--obstacles", type=int, default=10, help="number of random obstacles")
    parser.add_argument("--seed", type=int, help="random seed, for a reproducible grid")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    grid = Grid(width=args.width, height=args.height)
    grid.create_obstacles(args.obstacles)

    print(format_chars(to_chars(grid), color=not args.no_color))


if __name__ == "__main__":
    main()
