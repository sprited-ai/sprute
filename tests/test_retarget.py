import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODES = ROOT / "custom_nodes" / "sprute"


def load_retarget():
    """Import the node package's retarget module without its __init__, which needs ComfyUI."""
    package = importlib.util.spec_from_loader("sprute_nodes", loader=None, is_package=True)
    module = importlib.util.module_from_spec(package)
    module.__path__ = [str(NODES)]
    sys.modules.setdefault("sprute_nodes", module)
    return importlib.import_module("sprute_nodes.retarget")


@pytest.fixture(scope="module")
def retarget():
    return load_retarget()


def test_a_retargeted_loop_lasts_as_long_as_its_source(retarget):
    # jog-fwd is 28 frames at 30 fps: 22.4 frames at 24 fps.
    name, fps, loop, rotations, hips = retarget.retarget(
        ROOT / "motions" / "quaternius" / "jog-fwd.glb", "", ROOT / "assets" / "template-kun" / "template-kun.glb")
    assert loop is True
    assert len(hips) / fps == pytest.approx(28 / 30)
