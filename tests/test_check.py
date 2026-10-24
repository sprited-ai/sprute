import torch

from conftest import node_module

check = node_module("check")
layout = node_module("layout")


CELL = 8


def strip(colours, alpha=1.0, frames=1):
    """A strip whose cells are flat colours, one per direction, with uniform alpha."""
    rgb = torch.cat([torch.tensor(c).float().expand(frames, CELL, CELL, 3) for c in colours], dim=2)
    return rgb, torch.full(rgb.shape[:3], float(alpha))


COLOURS = [(i / 10, 0.2, 1 - i / 10) for i in range(8)]


def embed(images):
    """A stand-in embedding: the mean colour, so identical cells match and different cells do not."""
    return images.mean(dim=(1, 2)) - 0.5


def test_a_strip_that_matches_its_reference_passes():
    reference, reference_alpha = strip(COLOURS)
    frames, alpha = strip(COLOURS, frames=3)
    verdict = check.verdict(check.measure(frames, alpha, reference, reference_alpha, embed))
    assert all(v["pass"] for v in verdict.values())


def test_a_faded_direction_fails():
    reference, reference_alpha = strip(COLOURS)
    frames, alpha = strip(COLOURS, frames=3)
    alpha[:, :, CELL:2 * CELL] = 0.2                     # SE fades to a ghost
    verdict = check.verdict(check.measure(frames, alpha, reference, reference_alpha, embed))
    assert verdict["SE"]["reasons"] and "fades" in verdict["SE"]["reasons"]
    assert verdict["S"]["pass"]


def test_a_direction_showing_the_opposite_view_reads_as_turned_around():
    reference, reference_alpha = strip(COLOURS)
    turned = list(COLOURS)
    turned[layout.STRIP.index("NE")] = COLOURS[layout.STRIP.index("SW")]
    frames, alpha = strip(turned, frames=3)
    verdict = check.verdict(check.measure(frames, alpha, reference, reference_alpha, embed, directions=4))
    assert "turned around" in verdict["NE"]["reasons"]
    assert set(verdict) == {"SE", "NE", "NW", "SW"}


def test_side_views_are_not_judged_for_facing():
    reference, reference_alpha = strip(COLOURS)
    turned = list(COLOURS)
    turned[layout.STRIP.index("E")] = COLOURS[layout.STRIP.index("W")]
    frames, alpha = strip(turned, frames=3)
    verdict = check.verdict(check.measure(frames, alpha, reference, reference_alpha, embed))
    assert "turned around" not in verdict["E"]["reasons"]


def test_opposite_pairs_front_with_back():
    assert [check.opposite(n) for n in ("S", "SE", "NE", "W")] == ["N", "NW", "SW", "E"]
