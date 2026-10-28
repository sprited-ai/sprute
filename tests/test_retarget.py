import numpy as np
import pytest

from conftest import ROOT, node_module

TEMPLATE_KUN = ROOT / "assets" / "template-kun" / "template-kun.glb"


def test_a_retargeted_loop_lasts_as_long_as_its_source():
    # jog-fwd is 28 frames at 30 fps: 22.4 frames at 24 fps.
    name, fps, loop, rotations, hips = node_module("retarget").retarget(
        ROOT / "motions" / "quaternius" / "jog-fwd.glb", "", TEMPLATE_KUN)
    assert loop is True
    assert len(hips) / fps == pytest.approx(28 / 30)


def lowest_points(motion):
    """Template-kun's skinned min y per frame of a retargeted motion."""
    retarget = node_module("retarget")
    skeleton = retarget.Skeleton(TEMPLATE_KUN)
    node = next(n for n in skeleton.doc["nodes"] if "mesh" in n)
    attributes = skeleton.doc["meshes"][node["mesh"]]["primitives"][0]["attributes"]
    positions = skeleton.accessor(attributes["POSITION"]).astype(float)
    joints = skeleton.accessor(attributes["JOINTS_0"]).astype(int)
    weights = skeleton.accessor(attributes["WEIGHTS_0"]).astype(float)
    skin = skeleton.doc["skins"][node["skin"]]
    inverse_bind = skeleton.accessor(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
    _, _, _, rotations, hips = motion
    lowest = []
    for frame in range(len(hips)):
        rotation, translation = skeleton.rotation.copy(), skeleton.translation.copy()
        for role, values in rotations.items():
            rotation[skeleton.bone[role]] = values[frame]
        translation[skeleton.hips] = hips[frame]
        blend = ((skeleton.world(translation, rotation)[skin["joints"]] @ inverse_bind)[joints] * weights[..., None, None]).sum(1)
        lowest.append((np.einsum("vij,vj->vi", blend[:, :3, :3], positions) + blend[:, :3, 3])[:, 1].min())
    return np.array(lowest)


@pytest.mark.parametrize("clip", ["idle-talking", "crouch-idle"])
def test_a_standing_retarget_keeps_template_kun_on_the_ground(clip):
    # Quaternius' spine leans forward and his legs are longer: both used to sink Template-kun 2-6 cm.
    motion = node_module("retarget").retarget(ROOT / "motions" / "quaternius" / f"{clip}.glb", "", TEMPLATE_KUN)
    assert np.abs(lowest_points(motion)).max() < 0.003


def test_a_retargeted_jump_still_leaves_the_ground():
    motion = node_module("retarget").retarget(ROOT / "motions" / "quaternius" / "backflip.glb", "", TEMPLATE_KUN)
    assert lowest_points(motion).max() > 0.3
