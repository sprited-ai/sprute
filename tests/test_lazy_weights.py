import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deploy.replicate import lazy_weights as lazy


class LazyWeightsTests(unittest.TestCase):
    def test_stages_skip_unneeded_models(self):
        generate = lazy.required_models(dict(prompt="test", stop_after="generate"))
        self.assertIn("flux-fill", generate)
        self.assertNotIn("scail2", generate)
        animate = lazy.required_models(dict(image="strip.png", image_type="directions", stop_after="animate"))
        self.assertIn("scail2", animate)
        self.assertNotIn("flux-fill", animate)
        self.assertNotIn("anisora-high", animate)
        all_models = lazy.required_models(dict(prompt="test", stop_after="animate"))
        self.assertEqual(set(all_models), set().union(*lazy.STAGES.values()))

    def test_warm_reuse_and_corruption_recovery(self):
        data = b"valid weights"
        entry = dict(repo_id="test", filename="weights", revision="pinned", destination="weights",
                     size=len(data), sha256=hashlib.sha256(data).hexdigest())
        def download(*args, destination, **kwargs):
            destination.write_bytes(data)
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(lazy, "required_models", return_value=["test"]), \
             patch.object(lazy, "download_model", side_effect=download) as fetch:
            root = Path(folder)
            lazy.ensure_weights({}, root, manifest={"test": entry})
            lazy.ensure_weights({}, root, manifest={"test": entry})
            self.assertEqual(fetch.call_count, 1)
            (root / "weights").write_bytes(b"wrong weights")
            # Some container filesystems coalesce timestamps within one tick.
            os.utime(root / "weights", ns=(0, 0))
            lazy.ensure_weights({}, root, manifest={"test": entry})
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual((root / "weights").read_bytes(), data)

    def test_bad_download_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(lazy, "required_models", return_value=["test"]), \
             patch.object(lazy, "download_model", side_effect=lambda *a, destination, **k: destination.write_bytes(b"bad")):
            entry = dict(repo_id="test", filename="weights", revision="pinned", destination="weights", size=3, sha256="0" * 64)
            with self.assertRaisesRegex(RuntimeError, "integrity"):
                lazy.ensure_weights({}, Path(folder), manifest={"test": entry})
            self.assertFalse((Path(folder) / "weights").exists())

    def test_manifest_covers_workflow_weights(self):
        manifest = json.loads(lazy.MANIFEST.read_text())
        for stage, names in lazy.STAGES.items():
            destinations = {Path(manifest[name]["destination"]).name for name in names}
            graph = json.loads(Path(f"workflows/sprute-{stage}-character.api.json").read_text())
            used = {value for node in graph.values() for value in node["inputs"].values()
                    if isinstance(value, str) and value.endswith(".safetensors")}
            self.assertLessEqual(used, destinations)
            for name in names:
                self.assertEqual(len(manifest[name]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
