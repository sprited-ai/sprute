import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_nodes" / "sprute"))
import layout  # noqa: E402

CELL = 4


def labelled_strip(frames=2):
    """An eight-direction strip whose cells hold their strip index plus one, so every pixel says where it came from."""
    cells = [torch.full((frames, CELL, CELL, 3), float(index + 1)) for index in range(len(layout.STRIP))]
    return torch.cat(cells, dim=2)


def test_eight_directions_make_a_3x3_grid_with_an_empty_centre():
    grid = layout.strip_to_grid(labelled_strip(), empty=0.0)
    assert grid.shape == (2, 3 * CELL, 3 * CELL, 3)
    assert grid[0, CELL, CELL, 0] == 0.0
    assert grid[0, 0, 0, 0] == layout.STRIP.index("NW") + 1


def test_four_directions_make_a_2x2_grid_of_the_diagonals():
    grid = layout.strip_to_grid(labelled_strip(), empty=0.0, directions=4)
    assert grid.shape == (2, 2 * CELL, 2 * CELL, 3)
    corners = {name: grid[0, row * CELL, column * CELL, 0].item()
               for name, (row, column) in {"NW": (0, 0), "NE": (0, 1), "SW": (1, 0), "SE": (1, 1)}.items()}
    assert corners == {name: layout.STRIP.index(name) + 1 for name in corners}


@pytest.mark.parametrize("directions", [8, 4])
def test_cells_come_back_to_a_full_strip(directions):
    strip = labelled_strip()
    back = layout.cells_to_strip(layout.grid_to_cells(layout.strip_to_grid(strip, empty=0.0, directions=directions),
                                                      directions=directions), directions=directions)
    assert back.shape == strip.shape
    for index, name in enumerate(layout.STRIP):
        cell = back[:, :, index * CELL:(index + 1) * CELL]
        expected = strip[:, :, index * CELL:(index + 1) * CELL] if name in layout.drawn(directions) else torch.zeros_like(cell)
        assert torch.equal(cell, expected), name


def test_four_directions_are_the_diagonals_in_strip_order():
    assert layout.drawn(4) == ("SE", "NE", "NW", "SW")


def test_rejects_other_direction_counts():
    with pytest.raises(ValueError, match="directions"):
        layout.strip_to_grid(labelled_strip(), empty=0.0, directions=6)
