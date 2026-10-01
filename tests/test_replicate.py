"""Pipeline contracts without downloading models or running GPU inference."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
import predict
from deploy.replicate.metrics import PeakMemory
from deploy.replicate import smoke


class SmokeTests(unittest.TestCase):
    def response(self, value):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(value).encode()
        return response

    def test_private_model_is_rejected_before_prediction(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(smoke, 'urlopen', return_value=self.response({'visibility': 'private'})) as http:
            with self.assertRaisesRegex(RuntimeError, 'private-model'):
                smoke.run('v', 'test-token', Path(directory) / 'test')
            self.assertEqual(http.call_count, 1)

    def test_one_prediction_has_server_deadline(self):
        responses = [{'visibility': 'public'}, {'id': 'v'}, {'results': []},
                     {'id': 'p', 'status': 'succeeded'}]
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(smoke, 'urlopen', side_effect=[self.response(r) for r in responses]) as http:
            smoke.run('v', 'test-token', Path(directory) / 'test')
            request = http.call_args.args[0]
            self.assertEqual(request.get_header('Cancel-after'), '10m')
            self.assertEqual(json.loads(request.data)['input']['stop_after'], 'generate')
            self.assertEqual(sum(c.args[0].get_method() == 'POST' for c in http.call_args_list), 1)

    def test_uncertain_submission_is_not_retried(self):
        responses = [self.response(r) for r in
                     [{'visibility': 'public'}, {'id': 'v'}, {'results': []}]]
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(smoke, 'urlopen', side_effect=responses + [TimeoutError('network')]) as http:
            with self.assertRaises(TimeoutError):
                smoke.run('v', 'test-token', Path(directory) / 'test')
            self.assertEqual(http.call_count, 4)

    def test_poll_failure_cancels_known_prediction(self):
        responses = [self.response(r) for r in
                     [{'visibility': 'public'}, {'id': 'v'}, {'results': []},
                      {'id': 'p', 'status': 'starting'}]]
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(smoke.time, 'sleep'), \
             patch.object(smoke, 'urlopen', side_effect=responses + [OSError('network'), self.response({'status': 'canceled'})]) as http:
            with self.assertRaises(OSError):
                smoke.run('v', 'test-token', Path(directory) / 'test')
            self.assertTrue(http.call_args.args[0].full_url.endswith('/p/cancel'))


class PredictorTests(unittest.TestCase):
    def setUp(self):
        self.predictor = predict.Predictor()
        self.predictor.setup()
        self.predictor.output = Path(tempfile.mkdtemp(prefix='sprute-test-'))
        self.inputs = tempfile.TemporaryDirectory()
        self.image = Path(self.inputs.name) / 'upload.png'
        Image.new('RGBA', (64, 64)).save(self.image)

    def tearDown(self):
        self.inputs.cleanup()
        if self.predictor.output:
            import shutil
            shutil.rmtree(self.predictor.output, ignore_errors=True)

    def run_prediction(self, **overrides):
        inputs = dict(prompt='test', image=None, image_type='character',
                      stop_after='animate', motions='idle,walk,run', seed=42)
        inputs.update(overrides)
        return self.predictor.run_pipeline(**inputs)

    def fake_output(self, *args, **kwargs):
        path = kwargs['out'] / 'result.png'
        Image.new('RGBA', (64, 64)).save(path)
        return path

    def test_required_inputs(self):
        with self.assertRaisesRegex(ValueError, 'prompt or an image'):
            self.run_prediction(prompt=' ')
        with self.assertRaisesRegex(ValueError, 'before'):
            self.run_prediction(image=self.image, image_type='directions', stop_after='turntable')
        with self.assertRaisesRegex(ValueError, 'motions'):
            self.run_prediction(motions='jump')

    def test_full_pipeline_connects_files_and_runs_separate_motions(self):
        calls = []
        def stage(name):
            def execute(*args, **kwargs):
                calls.append((name, args, kwargs['seed']))
                return self.fake_output(*args, **kwargs)
            return execute
        with patch.object(predict, 'generate', side_effect=stage('generate')), \
             patch.object(predict, 'turntable', side_effect=stage('turntable')), \
             patch.object(predict, 'animate', side_effect=stage('animate')):
            self.run_prediction()
        self.assertEqual([c[0] for c in calls], ['generate', 'turntable', 'animate', 'animate', 'animate'])
        self.assertEqual([c[1][1] for c in calls[2:]], ['idle', 'walk', 'run'])
        self.assertTrue(all(c[2] == 42 for c in calls))
        self.assertEqual(calls[1][1][0], self.predictor.output / 'result.png')
        metrics = json.loads((self.predictor.output / 'metrics.json').read_text())
        self.assertEqual(len(metrics['stages']), 5)
        self.assertEqual(metrics['status'], 'succeeded')

    def test_character_skips_generate_and_stop_after_turntable(self):
        with patch.object(predict, 'generate') as generate, \
             patch.object(predict, 'turntable', side_effect=self.fake_output) as turntable, \
             patch.object(predict, 'animate') as animate:
            self.run_prediction(image=self.image, stop_after='turntable')
        generate.assert_not_called()
        animate.assert_not_called()
        turntable.assert_called_once()

    def test_directions_skips_earlier_stages_and_deduplicates_motions(self):
        with patch.object(predict, 'generate') as generate, \
             patch.object(predict, 'turntable') as turntable, \
             patch.object(predict, 'animate', side_effect=self.fake_output) as animate:
            self.run_prediction(image=self.image, image_type='directions', motions='run, run')
        generate.assert_not_called()
        turntable.assert_not_called()
        animate.assert_called_once()

    def test_random_seed(self):
        with patch.object(predict, 'generate', side_effect=self.fake_output) as generate:
            self.run_prediction(stop_after='generate', seed=-1)
        self.assertTrue(0 <= generate.call_args.kwargs['seed'] <= 4294967295)

    def test_scale_only_reaches_animation(self):
        with patch.object(predict, 'generate', side_effect=self.fake_output) as generate, \
             patch.object(predict, 'turntable', side_effect=self.fake_output) as turntable, \
             patch.object(predict, 'animate', side_effect=self.fake_output) as animate:
            self.run_prediction(scale=0.85)
        self.assertNotIn('scale', generate.call_args.kwargs)
        self.assertNotIn('scale', turntable.call_args.kwargs)
        self.assertEqual(animate.call_args.kwargs['scale'], 0.85)
        with self.assertRaises(ValueError):
            self.run_prediction(scale=float('nan'))

    def test_hosted_entry_uses_bounded_worker_and_isolates_outputs(self):
        previous = self.predictor.output
        (previous / 'old.png').touch()
        def worker(command, **kwargs):
            self.assertEqual(kwargs['timeout'], 600)
            request = Path(command[-1])
            data = json.loads(request.read_text())
            self.assertEqual(data['scale'], 0.95)
            (request.parent / 'sprite.png').touch()
        with patch.object(predict, 'run_bounded', side_effect=worker):
            files = self.predictor.predict(prompt='test', image=None, image_type='character',
                stop_after='generate', motions='run', seed=42, scale=0.95)
        self.assertFalse(previous.exists())
        self.assertEqual([p.name for p in files], ['sprite.png'])

    def test_failure_records_stage_and_stops_pipeline(self):
        with patch.object(predict, 'generate', side_effect=RuntimeError('inference failed')), \
             patch.object(predict, 'turntable') as turntable:
            with self.assertRaisesRegex(RuntimeError, 'inference failed'):
                self.run_prediction()
        turntable.assert_not_called()
        metrics = json.loads((self.predictor.output / 'metrics.json').read_text())
        self.assertEqual(metrics['status'], 'failed')
        self.assertEqual(metrics['stages'][0]['status'], 'failed')


class MemoryTests(unittest.TestCase):
    def test_peak_is_maximum_sample_not_last(self):
        nvml = MagicMock()
        nvml.nvmlDeviceGetCount.return_value = 1
        nvml.nvmlDeviceGetUUID.return_value = 'GPU-test'
        nvml.nvmlDeviceGetMemoryInfo.side_effect = [
            type('Memory', (), {'used': n})() for n in (100, 500, 200)]
        with patch.dict('sys.modules', {'pynvml': nvml}):
            with PeakMemory(interval=60) as meter:
                meter.sample()
                meter.sample()
        self.assertEqual(meter.result()['peak_device_memory_bytes'], {'GPU-test': 500})
        nvml.nvmlShutdown.assert_called_once()

    def test_missing_nvml_is_reported_not_zero_gpu(self):
        with patch.dict('sys.modules', {'pynvml': None}):
            with PeakMemory() as meter:
                pass
        self.assertEqual(meter.result()['peak_device_memory_bytes'], {})
        self.assertIsNotNone(meter.result()['telemetry_error'])
        self.assertFalse(meter.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
