"""CPU tests for direction/state identity and masks; optional torch attention test."""
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image

from sprute_media import (ORDER, GRID, colored_mask, cut_grid, prepare_animation,
                          reference_grid, strip)
from sprute_models import link

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
    def test_padded_keys_do_not_leak(self):
        try:
            import torch
        except ImportError:
            self.skipTest('torch not installed; preprocessing does not require it')
        from sprute_attention import sdpa
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
