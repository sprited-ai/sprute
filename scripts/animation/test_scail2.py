"""No inference or server required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from common import write, file_record
from scail2 import build_graph, execute, validate_server

class ScailTests(unittest.TestCase):
    def test_fast_and_baseline_graph(self):
        g=build_graph('ref.png','drive.mp4')
        self.assertEqual(g['8']['class_type'],'VHS_LoadVideo')
        self.assertEqual(g['12']['inputs']['steps'],8)
        self.assertEqual(g['12']['inputs']['cfg'],1)
        self.assertEqual(g['11']['inputs']['length'],81)
        self.assertNotIn('reference_image_mask',g['11']['inputs'])
        g=build_graph('ref.png','drive.mp4',recipe='baseline')
        self.assertNotIn('16',g)
        self.assertEqual(g['12']['inputs']['steps'],20)
        self.assertEqual(g['2']['inputs']['model'],['1',0])

    def test_paired_masks(self):
        with self.assertRaises(ValueError):build_graph('a','b',reference_mask='m')
        g=build_graph('a','b',reference_mask='m',driver_mask='v')
        self.assertEqual(g['18']['inputs']['frame_load_cap'],81)
        self.assertEqual(g['11']['inputs']['pose_video_mask'],['18',0])

    def test_uncertain_submission_never_reposts(self):
        with tempfile.TemporaryDirectory() as tmp,patch('scail2.json_request') as api:
            write(Path(tmp)/'submission-started.json',{'at':'test'})
            with self.assertRaisesRegex(RuntimeError,'Uncertain'):execute('server',{},tmp)
            api.assert_not_called()

    def test_completed_resume_uses_cache(self):
        with tempfile.TemporaryDirectory() as tmp,patch('scail2.json_request') as api:
            p=Path(tmp)/'animation.mp4';p.write_bytes(b'video');write(Path(tmp)/'output.json',file_record(p))
            self.assertEqual(execute('server',{},tmp),p);api.assert_not_called()
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'changed'):execute('server',{},tmp)

    def test_resume_existing_job_does_not_post(self):
        with tempfile.TemporaryDirectory() as tmp,patch('scail2.json_request') as api,patch('scail2.download') as download:
            write(Path(tmp)/'job.json',{'prompt_id':'original'})
            api.return_value={'original':{'status':{'status_str':'success'},'outputs':{'15':{'gifs':[{'filename':'result.mp4','type':'output','subfolder':''}]}}}}
            download.side_effect=lambda url,path:Path(path).write_bytes(b'video')
            execute('server',{},tmp)
            api.assert_called_once_with('server/history/original')

    def test_failed_job_is_not_resubmitted(self):
        with tempfile.TemporaryDirectory() as tmp,patch('scail2.json_request') as api:
            write(Path(tmp)/'job.json',{'prompt_id':'failed'})
            api.return_value={'failed':{'status':{'status_str':'error'}}}
            with self.assertRaisesRegex(RuntimeError,'failed'):execute('server',{},tmp)
            api.assert_called_once_with('server/history/failed')

if __name__=='__main__':unittest.main()
