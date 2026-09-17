"""Offline regression checks: no model requests, no charges."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from common import pin, read, write, digest
from media import ORDER, GRID, bounds, choose_loop, compose_reference, horizontal, save_webp, timings
from providers import replicate, encoded_spans

class PipelineTests(unittest.TestCase):
    def test_reference_horizontal_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sheet=Image.new('RGBA',(80*8,128))
            for i in range(8):
                sprite=Image.new('RGBA',(20,70),(i*25,40,180,255));sheet.alpha_composite(sprite,(i*80+30,30))
            sheet.save(root/'sheet.png')
            layout=compose_reference(root/'sheet.png',root/'grid.png')
            self.assertEqual(layout['padding'],[24,0])
            # Rebuild transparent version of the grid; inverse must restore exact slot positions.
            g=Image.new('RGBA',(384,384))
            for i,d in enumerate(ORDER):
                x,y=GRID[d];g.alpha_composite(sheet.crop((i*80,0,(i+1)*80,128)),(x*128+24,y*128))
            result,meta=horizontal([g],root/'sheet.png')
            self.assertEqual(result[0].tobytes(),sheet.tobytes())
            self.assertEqual(meta['cell'],[80,128])

    def test_odd_grid_edges_cover_all_pixels(self):
        self.assertEqual(bounds(640),[0,213,427,640])
        self.assertEqual(sum(b-a for a,b in zip(bounds(640),bounds(640)[1:])),640)

    def test_webp_timing_including_identical_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.webp';ds=timings(19,24,23)
            fs=[Image.new('RGBA',(16,16),(0,0,0,0)) for _ in ds]
            for f in fs:f.paste((255,0,0,255),(4,4,12,12))
            save_webp(p,fs,ds)
            self.assertEqual(sum(ds),792)
            self.assertEqual(timings(121,24)[-1],42)

    def test_loop_full_period_and_bounds(self):
        frames=[]
        for n in range(60):
            im=Image.new('RGBA',(64,64));im.paste((255,255,255,255),(n%12*3,5,n%12*3+8,30));frames.append(im)
        loop=choose_loop(frames,10,15)
        self.assertEqual(loop['period'],12)
        self.assertEqual(loop['seam_score'],0)
        with self.assertRaises(ValueError):choose_loop(frames,1,80)

    def test_static_and_duplicate_intermediate_frame_expansion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'frames.webp'
            frame=Image.new('RGB',(8,8),'red')
            frame.save(path,save_all=True,append_images=[frame]*3,duration=[100]*4,lossless=True)
            self.assertEqual(encoded_spans(path,4),[4])
            frame.save(path,lossless=True)
            self.assertEqual(encoded_spans(path,1),[1])

    def test_changed_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'plan.json';pin(p,{'seed':42})
            with self.assertRaises(RuntimeError):pin(p,{'seed':1})
            self.assertEqual(read(p),{'seed':42})

    def test_uncertain_submission_never_reposts(self):
        with tempfile.TemporaryDirectory() as tmp, patch('providers.token',return_value='dummy'), patch('providers.json_request') as api:
            root=Path(tmp);write(root/'submission-started.json',{'at':'test'})
            with self.assertRaisesRegex(RuntimeError,'Uncertain'):
                replicate(root,'example/model',{},[],[],'out.png',True)
            api.assert_not_called()

    def test_failed_prediction_never_reposts(self):
        with tempfile.TemporaryDirectory() as tmp, patch('providers.token',return_value='dummy'), patch('providers.json_request') as api:
            root=Path(tmp);write(root/'prediction.json',{'id':'saved','status':'failed','error':'test'})
            with self.assertRaisesRegex(RuntimeError,'No automatic retry'):
                replicate(root,'example/model',{},[],[],'out.png',True)
            api.assert_not_called()

    def test_successful_prediction_posts_once_and_redacts_input(self):
        with tempfile.TemporaryDirectory() as tmp, patch('providers.token',return_value='dummy'), \
             patch('providers.time.sleep'), patch('providers.json_request') as api, \
             patch('providers.download',side_effect=lambda url,path: Path(path).write_bytes(b'output')):
            root=Path(tmp)
            api.side_effect=[{'id':'one','status':'processing','input':{'secret':'not persisted'}},
                {'id':'one','status':'succeeded','output':'https://example.com/out.png','input':{'secret':'not persisted'}}]
            replicate(root,'example/model',{},[],[],'out.png',True)
            self.assertEqual(api.call_count,2)
            self.assertNotIn('input',read(root/'prediction.json'))
            replicate(root,'example/model',{},[],[],'out.png',True)
            self.assertEqual(api.call_count,2)

    def test_no_paid_flag_does_not_submit(self):
        with tempfile.TemporaryDirectory() as tmp, patch('providers.token',return_value='dummy'), patch('providers.json_request') as api:
            with self.assertRaisesRegex(RuntimeError,'allow-paid'):
                replicate(Path(tmp),'example/model',{},[],[],'out.png')
            api.assert_not_called()
            self.assertFalse((Path(tmp)/'submission-started.json').exists())

    def test_completed_output_reused_without_token(self):
        with tempfile.TemporaryDirectory() as tmp, patch('providers.token') as token:
            root=Path(tmp);(root/'out.png').write_bytes(b'fixture');write(root/'output.json',{'sha256':digest(root/'out.png')})
            self.assertEqual(replicate(root,'example/model',{},[],[],'out.png'),root/'out.png')
            token.assert_not_called()

if __name__=='__main__':unittest.main()
