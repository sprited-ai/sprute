from pathlib import Path

import numpy as np
import pytest

from conftest import ROOT, node_module

renderer = node_module("renderer")


@pytest.fixture(scope="module")
def model():
    return renderer.Model(ROOT / "assets" / "template-kun" / "template-kun.glb", "cpu")


def standing(top, bottom, height=256, width=256):
    """A strip of eight cells, each a character standing from row `top` to row `bottom`."""
    alpha = np.zeros((height, 8 * width))
    for direction in range(8):
        alpha[top:bottom, direction * width + 100:direction * width + 156] = 1
    return alpha


def test_measures_the_median_cell_so_one_raised_arm_does_not_move_it():
    alpha = standing(45, 221)
    alpha[10:45, 120:130] = 1
    assert renderer.standing_line(alpha) == (45 / 256, 221 / 256)


@pytest.mark.parametrize("top, bottom", [(45, 221), (60, 230), (20, 250)])
def test_stands_template_kun_as_tall_as_the_character_on_its_feet_line(model, top, bottom):
    framing = renderer.fit_framing(model, standing(top, bottom))
    rest_top, rest_bottom = renderer.rest_line(model, framing)
    assert rest_top * 256 == pytest.approx(top, abs=0.5)
    assert rest_bottom * 256 == pytest.approx(bottom, abs=0.5)


def test_keeps_the_default_framing_for_a_character_of_template_kuns_size(model):
    top, bottom = renderer.rest_line(model, renderer.DEFAULT_FRAMING)
    framing = renderer.fit_framing(model, standing(round(top * 256), round(bottom * 256)))
    assert framing.pixels_per_metre == pytest.approx(renderer.DEFAULT_FRAMING.pixels_per_metre, rel=0.01)
    assert framing.centre_height == pytest.approx(renderer.DEFAULT_FRAMING.centre_height, abs=0.01)
