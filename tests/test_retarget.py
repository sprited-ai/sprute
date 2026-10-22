import pytest

from conftest import ROOT, node_module

TEMPLATE_KUN = ROOT / "assets" / "template-kun" / "template-kun.glb"


def test_a_retargeted_loop_lasts_as_long_as_its_source():
    # jog-fwd is 28 frames at 30 fps: 22.4 frames at 24 fps.
    name, fps, loop, rotations, hips = node_module("retarget").retarget(
        ROOT / "motions" / "quaternius" / "jog-fwd.glb", "", TEMPLATE_KUN)
    assert loop is True
    assert len(hips) / fps == pytest.approx(28 / 30)
