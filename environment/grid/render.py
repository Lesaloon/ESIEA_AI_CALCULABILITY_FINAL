"""Text and enum representations of a grid, shared by the CLI and the API."""

from enum import StrEnum

from .grid import Grid

EMPTY = "."
OBSTACLE = "#"


class CellType(StrEnum):
    EMPTY = "empty"
    OBSTACLE = "obstacle"


_CELL_TYPES = {
    EMPTY: CellType.EMPTY,
    OBSTACLE: CellType.OBSTACLE,
}

# ANSI colors used only for terminal output.
_RESET = "\x1b[0m"
_COLORS = {
    EMPTY: "\x1b[2m",
    OBSTACLE: "\x1b[1;97m",
}


def to_chars(grid: Grid) -> list[str]:
    """Return one string per row (y), one character per cell (x).

    Obstacles are the nodes missing from the graph.
    """
    width, height = grid.width, grid.height
    # Start fully blocked and open the existing nodes: one pass over the graph,
    # no membership test per cell.
    cells = bytearray(OBSTACLE.encode() * (width * height))
    empty = ord(EMPTY)
    for x, y in grid.graph.nodes:
        cells[y * width + x] = empty

    text = cells.decode("ascii")
    return [text[y * width : (y + 1) * width] for y in range(height)]


def to_cells(grid: Grid) -> list[list[CellType]]:
    """Return empty/obstacle enum cells indexed by [y][x]."""
    return [[_CELL_TYPES[symbol] for symbol in row] for row in to_chars(grid)]


def format_chars(rows: list[str], color: bool = True) -> str:
    """Format rows for a terminal, spacing cells so they look roughly square."""
    table = str.maketrans({c: f"{code}{c}{_RESET}" for c, code in _COLORS.items()}) if color else None
    lines = (" ".join(row) for row in rows)
    if table:
        lines = (line.translate(table) for line in lines)
    return "\n".join(lines)
