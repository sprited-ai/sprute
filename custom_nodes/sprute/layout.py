"""Arrange the directions as a strip, how sprute saves them, or as a grid, how SCAIL2 reads them.

Eight directions make a 3x3 grid around an empty centre. Four directions, the diagonals only,
make a 2x2 grid, so SCAIL2 renders 4/9 of the pixels.
"""
import torch

STRIP = ("S", "SE", "E", "NE", "N", "NW", "W", "SW")          # left to right, counter-clockwise from south
GRIDS = {
    8: (3, ("NW", "N", "NE", "W", None, "E", "SW", "S", "SE")),  # row by row, around an empty centre
    4: (2, ("NW", "NE", "SW", "SE")),                            # the corners of the 3x3 grid
}


def grid_layout(directions: int) -> tuple[int, tuple[str | None, ...]]:
    if directions not in GRIDS:
        raise ValueError(f"directions must be one of {sorted(GRIDS)}; got {directions}")
    return GRIDS[directions]


def drawn(directions: int) -> tuple[str, ...]:
    """The directions a grid holds, in strip order."""
    _, grid = grid_layout(directions)
    return tuple(name for name in STRIP if name in grid)


def strip_to_grid(strip: torch.Tensor, empty: float, directions: int = 8) -> torch.Tensor:
    """Centre each direction in a square cell, padding with `empty`, then arrange the grid."""
    columns, grid = grid_layout(directions)
    frames, height, width = strip.shape[0], strip.shape[1], strip.shape[2] // len(STRIP)
    if strip.shape[2] != width * len(STRIP):
        raise ValueError(f"A strip's width must divide by {len(STRIP)}; this one is {strip.shape[2]} wide")
    side = max(height, width)
    top_padding, left_padding = (side - height) // 2, (side - width) // 2
    out = torch.full((frames, side * columns, side * columns, *strip.shape[3:]), empty, dtype=strip.dtype, device=strip.device)
    for cell, name in enumerate(grid):
        if name is not None:
            top = (cell // columns) * side + top_padding
            left = (cell % columns) * side + left_padding
            source = STRIP.index(name) * width
            out[:, top:top + height, left:left + width] = strip[:, :, source:source + width]
    return out


def grid_to_cells(grid: torch.Tensor, directions: int = 8) -> torch.Tensor:
    """(frames, n * height, n * width, ...) to (directions * frames, height, width, ...), in strip order:
    every frame of S, then of SE, and so on, skipping directions the grid does not hold."""
    columns, layout = grid_layout(directions)
    height, width = grid.shape[1] // columns, grid.shape[2] // columns
    if grid.shape[1] != height * columns or grid.shape[2] != width * columns:
        raise ValueError(f"A grid's width and height must divide by {columns}; this one is {grid.shape[2]}x{grid.shape[1]}")
    cells = []
    for name in drawn(directions):
        cell = layout.index(name)
        top, left = (cell // columns) * height, (cell % columns) * width
        cells.append(grid[:, top:top + height, left:left + width])
    return torch.cat(cells, dim=0)


def cells_to_strip(cells: torch.Tensor, directions: int = 8) -> torch.Tensor:
    """(directions * frames, height, width, ...) to (frames, height, 8 * width, ...). The reverse of grid_to_cells,
    as a full eight-direction strip; directions not drawn are left empty (zero, transparent)."""
    names = drawn(directions)
    frames = cells.shape[0] // len(names)
    if cells.shape[0] != frames * len(names):
        raise ValueError(f"The number of cells must divide by {len(names)}; there are {cells.shape[0]}")
    by_name = dict(zip(names, cells.split(frames, dim=0)))
    blank = torch.zeros_like(cells[:frames])
    return torch.cat([by_name.get(name, blank) for name in STRIP], dim=2)
