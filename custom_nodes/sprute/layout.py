"""Arrange the eight directions as a strip, how sprute saves them, or as a 3x3 grid, how SCAIL2 reads them."""
import torch

STRIP = ("S", "SE", "E", "NE", "N", "NW", "W", "SW")          # left to right, counter-clockwise from south
GRID = ("NW", "N", "NE", "W", None, "E", "SW", "S", "SE")     # row by row, around an empty centre


def strip_to_grid(strip: torch.Tensor, empty: float) -> torch.Tensor:
    """(frames, height, 8 * width, ...) to (frames, 3 * height, 3 * width, ...). The centre is filled with `empty`."""
    frames, height, width = strip.shape[0], strip.shape[1], strip.shape[2] // len(STRIP)
    if strip.shape[2] != width * len(STRIP):
        raise ValueError(f"A strip's width must divide by {len(STRIP)}; this one is {strip.shape[2]} wide")
    grid = torch.full((frames, height * 3, width * 3, *strip.shape[3:]), empty, dtype=strip.dtype, device=strip.device)
    for cell, name in enumerate(GRID):
        if name is not None:
            top, left, source = (cell // 3) * height, (cell % 3) * width, STRIP.index(name) * width
            grid[:, top:top + height, left:left + width] = strip[:, :, source:source + width]
    return grid


def grid_to_cells(grid: torch.Tensor) -> torch.Tensor:
    """(frames, 3 * height, 3 * width, ...) to (8 * frames, height, width, ...): every frame of S, then of SE, and so on."""
    height, width = grid.shape[1] // 3, grid.shape[2] // 3
    if grid.shape[1] != height * 3 or grid.shape[2] != width * 3:
        raise ValueError(f"A grid's width and height must divide by 3; this one is {grid.shape[2]}x{grid.shape[1]}")
    cells = []
    for name in STRIP:
        cell = GRID.index(name)
        top, left = (cell // 3) * height, (cell % 3) * width
        cells.append(grid[:, top:top + height, left:left + width])
    return torch.cat(cells, dim=0)


def cells_to_strip(cells: torch.Tensor) -> torch.Tensor:
    """(8 * frames, height, width, ...) to (frames, height, 8 * width, ...). The reverse of grid_to_cells, as a strip."""
    frames = cells.shape[0] // len(STRIP)
    if cells.shape[0] != frames * len(STRIP):
        raise ValueError(f"The number of cells must divide by {len(STRIP)}; there are {cells.shape[0]}")
    return torch.cat(list(cells.split(frames, dim=0)), dim=2)
