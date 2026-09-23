"""CPU tests for direction/state identity and masks; optional torch attention test."""
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image

from sprute_lib.media import (ORDER, GRID, colored_mask, cut_grid, prepare_animation,
                          reference_grid, strip)
from sprute_lib.models import link
from sprute import fingerprint_input, verify_outputs


class CompletionTests(unittest.TestCase):
    def test_later_missing_or_empty_frame_is_not_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'segments.json').write_text(json.dumps({'frames': 2}))
            (root/'frames').mkdir()
            (root/'frames/00000.png').write_bytes(b'first')
            (root/'animation-rgb.webp').write_bytes(b'video')
            job = {'prepared': str(root)}
            with self.assertRaisesRegex(FileNotFoundError, '00001.png'):
                verify_outputs('animate', root, job)
            last = root/'frames/00001.png'
            last.touch()
            with self.assertRaises(FileNotFoundError):
                verify_outputs('animate', root, job)
            last.write_bytes(b'last')
            verify_outputs('animate', root, job)


class FingerprintTests(unittest.TestCase):
    def test_digest_compatibility_order_and_changed_input(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, content in [('00002.png', b'second'), ('00001.png', b'first')]:
                (root/name).write_bytes(content)
            before = fingerprint_input(root)
            self.assertEqual(before, [
                dict(path=str((root/name).resolve()), sha256=hashlib.sha256(content).hexdigest())
                for name, content in [('00001.png', b'first'), ('00002.png', b'second')]])
            (root/'00002.png').write_bytes(b'changed')
            self.assertEqual(before[0], fingerprint_input(root)[0])
            self.assertNotEqual(before[1], fingerprint_input(root)[1])

    def test_missing_and_empty_inputs_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'No PNG frames'):
                fingerprint_input(temp)
            with self.assertRaises(FileNotFoundError):
                fingerprint_input(Path(temp)/'missing.png')


class CLIValidationTests(unittest.TestCase):
    def test_invalid_animation_options_fail_before_work_or_output_creation(self):
        import subprocess
        cli = Path(__file__).resolve().parents[1]/'scripts/sprute.py'
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'output'
            for command in ('run', 'animate'):
                for options, error in [(['--states', 'idle,typo'], 'Unknown state'),
                                       (['--states', 'idle,idle'], 'distinct states'),
                                       (['--size', '512'], 'equal cells')]:
                    args = [sys.executable, str(cli), command, '--out', str(out), *options]
                    if command == 'animate':
                        args += ['--standing', str(Path(temp)/'missing.png')]
                    result = subprocess.run(args, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn(error, result.stderr)
                    self.assertNotIn('Missing models', result.stderr)
                    self.assertFalse(out.exists())

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def standing(self):
        cells = []
        for i in range(8):
            im = Image.new('RGBA', (16, 16))
            im.paste((20+i*25, 50, 100, 255), (2, 2, 14, 14))
            cells.append(im)
        path = self.root/'standing.png'
        strip(cells).save(path)
        return path

    def test_grid_round_trip_preserves_direction_identity(self):
        grid = reference_grid(self.standing(), 96)
        cells = cut_grid([grid])
        for i, d in enumerate(ORDER):
            self.assertEqual(cells[d][0].getpixel((16, 16)), (20+i*25, 50, 100, 255))
        self.assertEqual(grid.getpixel((48, 48))[3], 0)

    def test_masks_encode_visibility_not_alpha_inverse(self):
        im = Image.new('RGBA', (2, 1))
        im.putpixel((0, 0), (100, 100, 100, 255))
        for replace in [False, True]:
            for ref in [False, True]:
                mask = colored_mask(im, replace, ref)
                self.assertEqual(mask.getpixel((0, 0)), (0, 0, 255))
                visible = (not replace) if ref else replace
                self.assertEqual(mask.getpixel((1, 0)), (255,)*3 if visible else (0,)*3)

    def test_state_selection_and_padding_never_drop_run_tail(self):
        driver = self.root/'driver';driver.mkdir()
        for i in range(82):
            Image.new('RGBA', (12, 12), (i, 40, 70, 255)).save(driver/f'{i:05d}.png')
        manifest = self.root/'driver.json'
        manifest.write_text(json.dumps(dict(frames=82, fps=24, segments=[
            dict(state='idle', start_frame=0, end_frame_exclusive=30),
            dict(state='walk', start_frame=30, end_frame_exclusive=62),
            dict(state='run', start_frame=62, end_frame_exclusive=82)])))
        out = self.root/'prepared'
        info = prepare_animation(self.standing(), driver, manifest,
                                  ['idle','walk','run'], out, size=96)
        self.assertEqual((info['frames'], info['inference_frames']), (82, 85))
        self.assertEqual(Image.open(out/'driver/00081.png').getpixel((0,0))[0], 81)
        self.assertEqual(Image.open(out/'driver/00084.png').getpixel((0,0))[0], 81)
        self.assertEqual(Image.open(out/'driver-mask/00000.png').getpixel((48,48)), (0,0,0))
        self.assertEqual(info['segments'][-1], dict(state='run', start=62, count=20))

    def test_link_does_not_replace_existing_model(self):
        one=self.root/'one';one.mkdir();two=self.root/'two';two.mkdir()
        root=self.root/'models'
        link(root,'flux',one)
        with self.assertRaises(FileExistsError):link(root,'flux',two)

    def test_unequal_grid_cells_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'equal cells'):
            prepare_animation('unused','unused','unused',[],self.root,size=512)

class AttentionTests(unittest.TestCase):
    def test_fp8_quantization_retains_weight_dtype_and_scale(self):
        try:
            import torch
        except ImportError:
            self.skipTest('torch not installed')
        from sprute_lib.fp8 import quantize_linears, FP8Linear
        model = torch.nn.Sequential(torch.nn.Linear(32, 32), torch.nn.LayerNorm(32))
        original = model[0].weight.detach().clone()
        norm = model[1]
        self.assertEqual(quantize_linears(model), 1)
        self.assertIsInstance(model[0], FP8Linear)
        self.assertIs(model[1], norm)
        model.to(dtype=torch.bfloat16)
        self.assertEqual(model[0].weight.dtype, torch.float8_e4m3fn)
        self.assertEqual(model[0].scale_weight.dtype, torch.float32)
        reconstructed = model[0].weight.float()*model[0].scale_weight
        relative_error = (original-reconstructed).norm()/original.norm()
        self.assertLess(relative_error.item(), 0.05)

    def test_padded_keys_do_not_leak(self):
        try:
            import torch
        except ImportError:
            self.skipTest('torch not installed; preprocessing does not require it')
        from sprute_lib.attention import sdpa
        torch.manual_seed(3)
        q=torch.randn(1,3,2,4);k=torch.randn(1,5,2,4);v=torch.randn(1,5,2,4)
        output=sdpa(q,k,v,k_lens=[2])
        k[:,2:]=9999;v[:,2:]=-9999
        torch.testing.assert_close(sdpa(q,k,v,k_lens=[2]),output)
        expected=torch.nn.functional.scaled_dot_product_attention(
            q.transpose(1,2),k[:,:2].transpose(1,2),v[:,:2].transpose(1,2)).transpose(1,2)
        torch.testing.assert_close(output,expected)

if __name__ == '__main__':
    unittest.main()
