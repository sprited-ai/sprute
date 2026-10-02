import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from deploy.replicate.weights import assemble_weights


class WeightPartsTests(unittest.TestCase):
    def test_restores_exact_bytes_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            parts = root / '.parts'
            parts.mkdir()
            (parts / 'a').write_bytes(b'first')
            (parts / 'b').write_bytes(b'second')
            entry = dict(destination='diffusion_models/test.safetensors',
                         parts=['a', 'b'], size=11,
                         sha256=hashlib.sha256(b'firstsecond').hexdigest())
            (parts / 'manifest.json').write_text(json.dumps([entry]))
            assemble_weights(root)
            target = root / entry['destination']
            self.assertEqual(target.read_bytes(), b'firstsecond')
            target.unlink()
            (parts / 'b').write_bytes(b'broken')
            with self.assertRaisesRegex(RuntimeError, 'integrity'):
                assemble_weights(root)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix('.safetensors.tmp').exists())
