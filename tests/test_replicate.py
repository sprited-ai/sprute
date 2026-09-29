"""Adapter contracts; no model downloads or GPU needed."""
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import predict
from deploy.replicate.metrics import PeakMemory


class PredictorTests(unittest.TestCase):
    def setUp(self):
        self.predictor = predict.Predictor()
        self.predictor.setup()

    def tearDown(self):
        if self.predictor.output:
            import shutil
            shutil.rmtree(self.predictor.output, ignore_errors=True)

    def run_prediction(self, **overrides):
        inputs = dict(operation="generate", prompt="test", image=None, motion="idle", seed=42)
        inputs.update(overrides)
        return self.predictor.predict(**inputs)

    def test_required_inputs(self):
        with self.assertRaisesRegex(ValueError, "requires a prompt"):
            self.run_prediction(prompt=" ")
        for operation in ("turntable", "animate"):
            with self.assertRaisesRegex(ValueError, "requires an image"):
                self.run_prediction(operation=operation)

    def test_generate_isolated_outputs_and_metrics(self):
        def generate(prompt, **kwargs):
            path = kwargs['out'] / '0001.character.png'
            path.write_bytes(b'test')
            return path
        with patch.object(predict, 'generate', side_effect=generate) as call:
            first = self.run_prediction()
            previous = first[0].parent
            metrics = json.loads((previous / 'metrics.json').read_text())
            self.assertEqual(metrics['seed'], 42)
            self.assertGreater(metrics['peak_process_tree_rss_bytes'], 0)
            self.assertIn('peak_device_memory_bytes', metrics)
            self.run_prediction(seed=-1)
            self.assertFalse(previous.exists())
            self.assertTrue(0 <= call.call_args.kwargs['seed'] <= 4294967295)

    def test_turntable_returns_all_artifacts(self):
        def turntable(image, **kwargs):
            for name in ('a.turntable.webp', 'a.directions.webp', 'a.directions.png'):
                (kwargs['out'] / name).write_bytes(b'test')
        with patch.object(predict, 'turntable', side_effect=turntable):
            paths = self.run_prediction(operation='turntable', image=Path('/tmp/a.png'))
        self.assertEqual(len(paths), 4)

    def test_animate_passes_motion(self):
        with patch.object(predict, 'animate') as call:
            self.run_prediction(operation='animate', image=Path('/tmp/directions.png'), motion='run')
        self.assertEqual(call.call_args.args, (Path('/tmp/directions.png'), 'run'))

    def test_failure_still_records_metrics(self):
        with patch.object(predict, 'generate', side_effect=RuntimeError('inference failed')):
            with self.assertRaisesRegex(RuntimeError, 'inference failed'):
                self.run_prediction()
        self.assertTrue((self.predictor.output / 'metrics.json').exists())


class MemoryTests(unittest.TestCase):
    def test_peak_is_maximum_sample_not_last(self):
        nvml = MagicMock()
        nvml.nvmlDeviceGetCount.return_value = 1
        nvml.nvmlDeviceGetUUID.return_value = "GPU-test"
        nvml.nvmlDeviceGetMemoryInfo.side_effect = [
            type("Memory", (), {"used": n})() for n in (100, 500, 200)
        ]
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
