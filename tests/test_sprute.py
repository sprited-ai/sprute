"""CPU tests for direction/state identity and masks; optional torch attention test."""
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image

from sprute_lib.media import (ORDER, GRID, colored_mask, cut_grid, prepare_animation,
                          reference_grid, strip, narrow_grid)
from sprute_lib.models import link
from sprute import fingerprint_input, verify_outputs


class CompletionTests(unittest.TestCase):
    def test_animation_infers_each_state_separately_then_exports_in_order(self):
        from unittest.mock import patch
        import sprute
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            standing = root/'standing.png'
            standing.write_bytes(b'input')
            args = sprute.parser().parse_args(['animate', '--standing', str(standing),
                '--out', str(root/'out'), '--states', 'idle,walk,run'])
            calls = []
            def prepare(standing, driver, manifest, states, dest, *options):
                self.assertEqual(len(states), 1)
                dest.mkdir(parents=True)
                count = {'idle': 30, 'walk': 32, 'run': 20}[states[0]]
                (dest/'segments.json').write_text(json.dumps(dict(fps=24, frames=count,
                    inference_frames=((count-1+3)//4)*4+1,
                    segments=[dict(state=states[0], start=0, count=count)])))
            def worker(args, stage, out, **settings):
                calls.append((stage, out.name))
                if stage == 'animate':
                    info = json.loads((Path(settings['prepared'])/'segments.json').read_text())
                    self.assertEqual(len(info['segments']), 1)
                    (out/'frames').mkdir(parents=True)
                    for i in range(info['frames']):
                        (out/'frames'/f'{i:05d}.png').write_bytes(f'{out.name}:{i}'.encode())
                else:
                    frames = Path(settings['video'])
                    self.assertEqual((frames/'00029.png').read_bytes(), b'idle:29')
                    self.assertEqual((frames/'00030.png').read_bytes(), b'walk:0')
                    self.assertEqual((frames/'00062.png').read_bytes(), b'run:0')
                    self.assertEqual(len(list(frames.glob('*.png'))), 82)
                    self.assertTrue((frames/'00062.png').samefile(root/'out/inference/run/frames/00000.png'))
            with patch.object(sprute, 'prepare_animation', side_effect=prepare), \
                 patch.object(sprute, 'run_worker', side_effect=worker):
                sprute.animate(args)
            self.assertEqual(calls, [('animate', 'idle'), ('animate', 'walk'),
                                    ('animate', 'run'), ('export', 'animations')])

    def test_export_rejects_invalid_segment_before_loading_frames_or_model(self):
        from unittest.mock import patch
        from sprute_lib import inference
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root/'segments.json'
            for start, count in ((-1, 2), (0, 0), (8, 3)):
                manifest.write_text(json.dumps(dict(frames=10, segments=[
                    dict(state='run', start=start, count=count)])))
                with patch.object(inference, 'read_frames') as read, \
                        patch.object(inference, 'ToonOut') as matte:
                    with self.assertRaisesRegex(ValueError, 'Invalid export segment bounds: run'):
                        inference.export(dict(segments=str(manifest), video='unused'), root, root/'out')
                    read.assert_not_called()
                    matte.assert_not_called()
                self.assertFalse((root/'out').exists())

    def test_temporary_run_publishes_only_assets_and_cleans_work(self):
        from unittest.mock import patch
        import sprute
        with tempfile.TemporaryDirectory() as temp:
            args = sprute.parser().parse_args([
                'run', '--out', str(Path(temp)/'character'), '--precision', 'fp8',
                '--turntable-prompt', 'turn around', '--quality', '80', '--replace'])
            work_dirs = []

            def fake_pipeline(job):
                work_dirs.append(job.out)
                self.assertEqual(job.out.parent.parent, args.out.parent.resolve())
                self.assertFalse(args.out.exists())
                for folder, name in [('reference', 'reference.png'), ('standing', 'standing.png')]:
                    (job.out/folder).mkdir(parents=True)
                    (job.out/folder/name).write_bytes(b'asset')
                (job.out/'standing/selection.json').write_text(json.dumps({
                    'indices': [0, 70, 60, 50, 40, 30, 20, 10],
                    'note': 'Approximate directions.'}))
                output = job.out/'motion/animations'
                (output/'idle').mkdir(parents=True)
                (output/'animation.json').write_text(json.dumps({'segments': [{'state': 'idle'}]}))
                for direction in [*ORDER, 'horizontal']:
                    (output/'idle'/f'{direction}.webp').write_bytes(b'animation')
                (output/'intermediate.png').write_bytes(b'not for export')

            with patch.object(sprute, 'run_pipeline', side_effect=fake_pipeline):
                sprute.run(args)
            self.assertEqual({p.name for p in args.out.iterdir()},
                             {'reference.png', 'standing.png', 'idle', 'manifest.json'})
            self.assertEqual(len(list((args.out/'idle').glob('*.webp'))), 9)
            self.assertFalse(work_dirs[0].parent.exists())
            manifest = json.loads((args.out/'manifest.json').read_text())
            self.assertEqual(manifest['precision'], 'fp8')
            self.assertEqual(manifest['turntable_prompt'], 'turn around')
            self.assertEqual(manifest['animation_prompt'], '')
            self.assertEqual(manifest['quality'], 80)
            self.assertTrue(manifest['replacement'])
            self.assertEqual(manifest['standing_selection']['indices'],
                             [0, 70, 60, 50, 40, 30, 20, 10])

    def test_failed_temporary_run_leaves_no_output(self):
        from unittest.mock import patch
        import sprute
        with tempfile.TemporaryDirectory() as temp:
            args = sprute.parser().parse_args(['run', '--out', str(Path(temp)/'character')])
            work_dirs = []
            def fail(job):
                work_dirs.append(job.out)
                job.out.mkdir()
                raise failure
            for failure in (RuntimeError('inference failed'), KeyboardInterrupt()):
                with patch.object(sprute, 'run_pipeline', side_effect=fail):
                    with self.assertRaises(type(failure)):
                        sprute.run(args)
                self.assertFalse(args.out.exists())
                self.assertFalse(work_dirs[-1].parent.exists())

    def test_missing_turntable_selection_is_not_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ['standing.png', 'turntable.webp', *[f'{d}.png' for d in ORDER]]:
                (root/name).write_bytes(b'asset')
            with self.assertRaisesRegex(FileNotFoundError, 'selection.json'):
                verify_outputs('turntable', root, {})
            (root/'selection.json').write_text('{}')
            verify_outputs('turntable', root, {})

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
    def test_source_setup_can_retry_after_failed_fetch(self):
        import subprocess
        from unittest.mock import patch
        from sprute_lib import models
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'source'
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), '-c', 'user.name=Test',
                '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty',
                '-qm', 'fixture'], check=True)
            revision = subprocess.check_output(['git', '-C', str(source),
                'rev-parse', 'HEAD'], text=True).strip()
            destination = root/'models'
            with patch.dict(models.SOURCES, {'fixture': (str(root/'missing'), revision)}, clear=True):
                with self.assertRaises(subprocess.CalledProcessError):
                    models.setup_sources(destination)
            self.assertFalse((destination/'_sources/fixture').exists())
            with patch.dict(models.SOURCES, {'fixture': (str(source), revision)}, clear=True):
                models.setup_sources(destination)
                models.setup_sources(destination)
            actual = subprocess.check_output(['git', '-C', str(destination/'_sources/fixture'),
                'rev-parse', 'HEAD'], text=True).strip()
            self.assertEqual(actual, revision)

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
    def test_invalid_memory_limit_fails_before_work(self):
        import subprocess
        cli = Path(__file__).resolve().parents[1]/'scripts/sprute.py'
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'output'
            for value in ('0', '-1', 'nan', 'inf'):
                result = subprocess.run([sys.executable, str(cli), 'run',
                    '--vram-limit-gib', value, '--out', str(out)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn('--vram-limit-gib', result.stderr)
                self.assertFalse(out.exists())

    def test_invalid_seed_fails_before_loading_or_creating_output(self):
        import subprocess
        cli = Path(__file__).resolve().parents[1]/'scripts/sprute.py'
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'output'
            for seed in ('-1', str(2**64)):
                result = subprocess.run([sys.executable, str(cli), 'run',
                    '--seed', seed, '--out', str(out)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn('--seed must', result.stderr)
                self.assertNotIn('Missing models', result.stderr)
                self.assertFalse(out.exists())

    def test_pipeline_rejects_missing_inputs_before_model_loading(self):
        from unittest.mock import patch
        import sprute
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for option in ('--driver', '--image', '--template', '--text-encoder-fp8'):
                with self.subTest(option=option):
                    missing = root/'missing'
                    args = sprute.parser().parse_args([
                        'run', '--out', str(root/'out'), option, str(missing)])
                    with patch.object(sprute.models, 'require') as require, \
                            patch.object(sprute, 'run_worker') as worker:
                        with self.assertRaises(FileNotFoundError):
                            sprute.run_pipeline(args)
                        require.assert_not_called()
                        worker.assert_not_called()
                    self.assertFalse(args.out.exists())

    def test_pipeline_rejects_directories_as_input_files_before_loading(self):
        from unittest.mock import patch
        import sprute
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for option in ('--driver', '--image', '--template', '--manifest', '--text-encoder-fp8'):
                with self.subTest(option=option):
                    args = sprute.parser().parse_args([
                        'run', '--out', str(root/'out'), option, str(root)])
                    with patch.object(sprute.models, 'require') as require, \
                            patch.object(sprute, 'run_worker') as worker:
                        with self.assertRaisesRegex(ValueError, 'Expected an input file'):
                            sprute.run_pipeline(args)
                        require.assert_not_called()
                        worker.assert_not_called()
                    self.assertFalse(args.out.exists())

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
    def test_grid_requires_equal_cells_and_preserves_rectangular_dimensions(self):
        for size in ((769, 768), (768, 767)):
            with self.assertRaisesRegex(ValueError, '3 equal rows and columns'):
                cut_grid([Image.new('RGBA', size)])
        cells = cut_grid([Image.new('RGBA', (576, 768))])
        self.assertEqual(set(cells), set(ORDER))
        self.assertTrue(all(frames[0].size == (192, 256) for frames in cells.values()))

    def test_narrow_grid_preserves_pixels_and_rejects_clipping(self):
        source = Image.new('RGBA', (192, 192))
        for i, direction in enumerate(GRID):
            if direction:
                x, y = i%3*64, i//3*64
                source.paste((i*20, 80, 150, 255), (x+24, y+8, x+40, y+60))
        packed = narrow_grid(source, 32)
        self.assertEqual(packed.size, (96, 192))
        for i in range(9):
            x,y=i%3,i//3
            self.assertEqual(packed.crop((x*32,y*64,(x+1)*32,(y+1)*64)).tobytes(),
                             source.crop((x*64+16,y*64,x*64+48,(y+1)*64)).tobytes())
        source.putpixel((15, 10), (255, 255, 255, 1))
        with self.assertRaisesRegex(ValueError, 'clip NW'):
            narrow_grid(source, 32)

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

    def test_reference_rejects_direction_without_mask_foreground(self):
        path = self.standing()
        for alpha in (0, 127):
            with Image.open(path) as source:
                image = source.convert('RGBA')
            image.paste((255, 0, 0, alpha), (0, 0, 16, 16))
            image.save(path)
            with self.assertRaisesRegex(ValueError, 'Standing strip S has no foreground'):
                reference_grid(path, 96)

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
