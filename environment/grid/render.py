"""Text representation of a grid, shared by the CLI and the API."""

from .grid import Grid

EMPTY = "."
OBSTACLE = "#"
AGENT = "A"

# ANSI colors used only for terminal output.
_RESET = "\x1b[0m"
_COLORS = {
    EMPTY: "\x1b[2m",
    OBSTACLE: "\x1b[1;97m",
    AGENT: "\x1b[1;31m",
}


def to_chars(grid: Grid, markers: dict[tuple[int, int], str] | None = None) -> list[str]:
    """Return one string per row (y), one character per cell (x).

    Obstacles are the nodes missing from the graph. `markers` places extra
    symbols, such as the agent, on top of the cells.
    """
    width, height = grid.width, grid.height
    # Start fully blocked and open the existing nodes: one pass over the graph,
    # no membership test per cell.
    cells = bytearray(OBSTACLE.encode() * (width * height))
    empty = ord(EMPTY)
    for x, y in grid.graph.nodes:
        cells[y * width + x] = empty
    for (x, y), symbol in (markers or {}).items():
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"Marker {(x, y)} is outside the grid")
        cells[y * width + x] = ord(symbol)

    text = cells.decode("ascii")
    return [text[y * width : (y + 1) * width] for y in range(height)]


def format_chars(rows: list[str], color: bool = True) -> str:
    """Format rows for a terminal, spacing cells so they look roughly square."""
    table = str.maketrans({c: f"{code}{c}{_RESET}" for c, code in _COLORS.items()}) if color else None
    lines = (" ".join(row) for row in rows)
    if table:
        lines = (line.translate(table) for line in lines)
    return "\n".join(lines)
