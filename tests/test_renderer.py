import numpy as np
import torch

from conftest import ROOT, node_module

renderer = node_module("renderer")


def test_stands_template_kun_like_a_sprute_character():
    # 0018 stands with its head at y=46 and its feet at y=222 in a 256-pixel cell; the driver should match.
    model = renderer.Model(ROOT / "assets" / "template-kun" / "template-kun.glb", "cpu")
    positions, _ = model.skinned(model.rest)
    centre = torch.tensor([0.0, renderer.CENTRE_HEIGHT, 0.0])
    tops, bottoms = [], []
    for direction in range(8):
        y = 256 * (0.5 + renderer.PIXELS_PER_METRE * ((positions - centre) @ renderer.camera(direction, "cpu").T)[:, 1])
        tops.append(float(y.min())); bottoms.append(float(y.max()))
    assert abs(np.median(tops) - 46) < 1
    assert abs(np.median(bottoms) - 222) < 1
