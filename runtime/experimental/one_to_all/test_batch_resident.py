"""CPU-only checks for resident batch lifecycle; GPU equivalence is experiment 371."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import batch


class ResidentBatchTests(unittest.TestCase):
    def test_cli_os_signals_finish_direction_before_exit(self):
        import select
        import signal
        import subprocess
        import sys
        code = '''
import batch, sys, time
from pathlib import Path
plan = {d: {'conditioning': '/cache/' + d, 'seed': 42, 'prompt': '', 'inputFiles': {}} for d in batch.DIRECTIONS}
batch.validate_plan = lambda path: plan
batch.validate_cache = lambda path: {'files': {}}
def generate(conditioning, runtime, output, **options):
    print('ready', file=sys.__stdout__, flush=True)
    time.sleep(0.5)
    output.mkdir()
    (output / 'finished').write_text('yes')
batch.generate = generate
def verify(output):
    assert (output / 'finished').read_text() == 'yes'
batch.verify_result = verify
batch.main()
'''
        for sig in [signal.SIGINT, signal.SIGTERM]:
            with self.subTest(signal=sig), tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / 'run'
                process = subprocess.Popen(
                    [sys.executable, '-c', code, '--plan', 'unused', '--runtime', folder,
                     '--output', str(output), '--resident'],
                    cwd=Path(batch.__file__).parent, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True)
                try:
                    self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'CLI did not become ready')
                    self.assertEqual(process.stdout.readline().strip(), 'ready')
                    process.send_signal(sig)
                    stdout, stderr = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 128 + sig, stderr)
                    self.assertIn('Paused.', stdout)
                    self.assertIn('Stopping after', stderr)
                    state = json.loads((output / 'state.json').read_text())
                    self.assertEqual(state['completed'], ['S'])
                    self.assertEqual(state['status'], 'paused')
                    self.assertFalse((output / 'SE').exists())
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.communicate()

    def test_stop_request_finishes_current_direction_then_pauses(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'run'
            plan = {d: {'conditioning': '/cache/' + d, 'seed': 42,
                        'prompt': '', 'inputFiles': {}} for d in batch.DIRECTIONS}
            stopped = []
            def generate(*args, **kwargs):
                stopped.append(True)
            with patch.object(batch, 'validate_cache', return_value={'files': {}}), \
                 patch.object(batch, 'generate', side_effect=generate) as generate_call, \
                 patch.object(batch, 'verify_result') as verify:
                result = batch.run_plan(plan, folder, output, resident=True,
                                        stop_requested=lambda: bool(stopped))
            self.assertEqual(result, 'paused')
            self.assertEqual(generate_call.call_count, 1)
            verify.assert_called_once_with(output / 'S')
            state = json.loads((output / 'state.json').read_text())
            self.assertEqual(state['status'], 'paused')
            self.assertEqual(state['completed'], ['S'])
            self.assertIsNone(state['active'])

    def test_live_lock_prevents_resume_before_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            with (output / '.batch.lock').open('a') as lock:
                batch.fcntl.flock(lock, batch.fcntl.LOCK_EX | batch.fcntl.LOCK_NB)
                with patch.object(batch, 'generate') as generate:
                    with self.assertRaisesRegex(ValueError, 'Another batch process'):
                        batch.run_plan({}, folder, output, resume=True)
                    generate.assert_not_called()

    def test_resume_skips_complete_child_and_refuses_partial_or_changed_child(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'run'
            output.mkdir()
            plan = {d: {'conditioning': '/cache/' + d, 'seed': 42,
                        'prompt': '', 'inputFiles': {}} for d in batch.DIRECTIONS}
            (output / 'plan.json').write_text(json.dumps(plan))
            (output / 'state.json').write_text(json.dumps({'runtime': str(Path(folder).resolve()), 'completed': ['S']}))
            child = output / 'S'
            (child / 'output').mkdir(parents=True)
            hashes = {}
            for i in range(65):
                name = f'frame_{i:06d}.png'
                # The verifier checks byte integrity; image decoding belongs to generate.
                (child / 'output' / name).write_bytes(b'fixture')
                hashes[name] = hashlib.sha256(b'fixture').hexdigest()
            (child / 'output-hashes.json').write_text(json.dumps(hashes))
            (child / 'state.json').write_text(json.dumps({'status': 'complete', 'frames': 65}))
            (child / 'run.json').write_text(json.dumps(plan['S']))
            with patch.object(batch, 'validate_cache', return_value={'files': {}}), \
                 patch.object(batch, 'generate', side_effect=RuntimeError('stop at next direction')) as generate:
                with self.assertRaisesRegex(RuntimeError, 'stop at next direction'):
                    batch.run_plan(plan, folder, output, resident=True, resume=True)
                self.assertEqual(generate.call_count, 1)
                self.assertEqual(generate.call_args.args[2].name, 'SE')
            (output / 'SE').mkdir()
            with patch.object(batch, 'generate') as generate:
                with self.assertRaises(OSError):
                    batch.run_plan(plan, folder, output, resident=True, resume=True)
                generate.assert_not_called()
            (output / 'SE').rmdir()
            (child / 'output' / 'frame_000000.png').write_bytes(b'changed')
            with patch.object(batch, 'generate') as generate:
                with self.assertRaisesRegex(ValueError, 'hash differs'):
                    batch.run_plan(plan, folder, output, resident=True, resume=True)
                generate.assert_not_called()

    def test_reuses_one_cache_and_keeps_each_direction_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'run'
            plan = {d: {'conditioning': '/cache/' + d, 'seed': i,
                        'prompt': 'view ' + d, 'inputFiles': {}}
                    for i, d in enumerate(batch.DIRECTIONS)}
            calls = []
            def generate(conditioning, runtime, destination, **options):
                cache = options.pop('pipe_cache')
                if calls:
                    self.assertIs(cache, calls[0][3])
                    self.assertTrue(cache['loaded'])
                cache['loaded'] = True
                calls.append((conditioning, destination.name, options, cache))
            with patch.object(batch, 'validate_cache', return_value={'files': {}}), \
                 patch.object(batch, 'generate', side_effect=generate), \
                 patch.object(batch, 'verify_result'), \
                 patch.object(batch.subprocess, 'run') as subprocess_run:
                batch.run_plan(plan, folder, output, resident=True)
                subprocess_run.assert_not_called()
            self.assertEqual(len(calls), 8)
            for i, (conditioning, direction, options, _) in enumerate(calls):
                self.assertEqual(conditioning, '/cache/' + direction)
                self.assertEqual(options, {'seed': i, 'prompt': 'view ' + direction})
            state = json.loads((output / 'state.json').read_text())
            self.assertEqual(state['status'], 'complete')
            self.assertEqual(state['completed'], batch.DIRECTIONS)

    def test_failure_stops_without_retry_and_restores_output_streams(self):
        import sys
        stdout, stderr = sys.stdout, sys.stderr
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'run'
            plan = {d: {'conditioning': '/cache/' + d, 'seed': 42,
                        'prompt': '', 'inputFiles': {}} for d in batch.DIRECTIONS}
            with patch.object(batch, 'validate_cache', return_value={'files': {}}), \
                 patch.object(batch, 'generate', side_effect=[None, RuntimeError('GPU failed')]) as generate, \
                 patch.object(batch, 'verify_result'):
                with self.assertRaisesRegex(RuntimeError, 'GPU failed'):
                    batch.run_plan(plan, folder, output, resident=True)
            self.assertEqual(generate.call_count, 2)
            state = json.loads((output / 'state.json').read_text())
            self.assertEqual(state['status'], 'failed')
            self.assertEqual(state['completed'], ['S'])
            self.assertEqual(state['active'], 'SE')
            self.assertIs(sys.stdout, stdout)
            self.assertIs(sys.stderr, stderr)


if __name__ == '__main__':
    unittest.main()
