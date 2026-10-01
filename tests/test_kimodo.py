"""Coordinate checks without loading ComfyUI or a Kimodo model."""
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
package = ModuleType("sprute_motion_test")
package.__path__ = [str(ROOT / "custom_nodes" / "sprute")]
sys.modules[package.__name__] = package
adapter = importlib.import_module(package.__name__ + ".kimodo")


class KimodoTests(unittest.TestCase):
    def motion(self):
        names = list(dict.fromkeys(adapter.BONES.values()))
        neutral = np.zeros((len(names), 3))
        neutral[names.index("LeftToeBase"), 1] = -1
        return SimpleNamespace(joint_names=names, neutral_joints=neutral, fps=30,
                               output_dict={
                                   "global_rot_mats": np.broadcast_to(np.eye(3), (1, 3, len(names), 3, 3)).copy(),
                                   "root_positions": np.array([[[0, 1, 0], [1, 1, 2], [2, 1, 4]]], dtype=float),
                               })

    def test_floor_relative_roots_preserve_standing_height_and_remove_travel(self):
        model = ROOT / "assets/template-kun/template-kun.glb"
        target = adapter.retarget.Skeleton(model)
        _, fps, loop, rotations, hips = adapter.adapt(self.motion(), model)
        self.assertEqual(fps, 30)
        self.assertFalse(loop)
        np.testing.assert_allclose(hips, np.broadcast_to(target.translation[target.hips], hips.shape), atol=1e-6)
        self.assertEqual(set(rotations), set(adapter.BONES))

    def test_bad_samples_are_rejected(self):
        motion = self.motion()
        motion.output_dict["global_rot_mats"][0, 0, 0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "non-finite"):
            adapter.adapt(motion, ROOT / "assets/template-kun/template-kun.glb")


if __name__ == "__main__":
    unittest.main()
