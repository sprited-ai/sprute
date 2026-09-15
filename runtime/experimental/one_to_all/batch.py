"""Validate and sequentially generate an explicit eight-direction experiment."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import fcntl
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
from generate import validate_cache, generate

DIRECTIONS = ['S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW']


def validate_plan(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    items = data['directions']
    if not isinstance(items, dict) or set(items) != set(DIRECTIONS):
        raise ValueError('Plan must contain exactly S, SE, E, NE, N, NW, W, SW')
    plan = {}
    for direction in DIRECTIONS:
        item = items[direction]
        seed, prompt = item.get('seed', 42), item.get('prompt', '')
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
            raise ValueError(f'Invalid seed for {direction}')
        if not isinstance(prompt, str):
            raise ValueError(f'Invalid prompt for {direction}')
        cache = (path.parent / item['conditioning']).resolve()
        metadata = validate_cache(cache)
        plan[direction] = {'conditioning': str(cache), 'seed': seed, 'prompt': prompt,
                           'inputFiles': metadata['files']}
    return plan


def verify_result(folder):
    state = json.loads((folder / 'state.json').read_text())
    if state['status'] != 'complete' or state['frames'] != 65:
        raise ValueError('Child did not complete 65 frames')
    hashes = json.loads((folder / 'output-hashes.json').read_text())
    frames = sorted((folder / 'output').rglob('frame_*.png'))
    if len(frames) != 65:
        raise ValueError('Child output frame count differs')
    for frame in frames:
        name = str(frame.relative_to(folder / 'output'))
        if hashlib.sha256(frame.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError(f'Child frame hash differs: {name}')


def run_plan(plan, runtime, output, *, runner=None, resident=False, resume=False, stop_requested=None):
    output = Path(output).absolute()
    if resume and not output.is_dir():
        raise ValueError('Resume requires an existing batch folder')
    output.mkdir(exist_ok=resume)
    # OS lock releases on process exit; never infer liveness from stale JSON.
    with (output / ".batch.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another batch process owns this output")
        return _run_plan(plan, runtime, output, runner=runner, resident=resident, resume=resume, stop_requested=stop_requested)


def _run_plan(plan, runtime, output, *, runner=None, resident=False, resume=False, stop_requested=None):
    if resident and runner is not None:
        raise ValueError('Resident mode cannot use a subprocess runner')
    output = Path(output).absolute()
    runtime = Path(runtime).resolve()
    completed = []
    if resume:
        saved = json.loads((output / 'state.json').read_text())
        if json.loads((output / 'plan.json').read_text()) != plan or saved.get('runtime') != str(runtime):
            raise ValueError('Saved plan or runtime differs; use a new output folder')
        # Verify every existing child before starting anything new. Partial children
        # require investigation; never erase them or automatically retry inference.
        for direction in DIRECTIONS:
            if (output / direction).exists():
                verify_result(output / direction)
                receipt = json.loads((output / direction / 'run.json').read_text())
                item = plan[direction]
                if any(receipt.get(k) != item[k] for k in ['seed', 'prompt', 'inputFiles']):
                    raise ValueError(f'Saved direction differs from plan: {direction}')
                completed.append(direction)
        if any(d not in completed for d in saved.get('completed', [])):
            raise ValueError('Previously completed output is missing')
    else:
        (output / 'plan.json').write_text(json.dumps(plan, indent=2))
    state = {'status': 'running', 'completed': completed, 'active': None,
             'started': time.time(), 'resident': resident, 'runtime': str(runtime)}
    if resume:
        state['previousAttempts'] = saved.get('previousAttempts', []) + [
            {k: v for k, v in saved.items() if k != 'previousAttempts'}]
    pipe_cache = {} if resident else None
    def save():
        temp = output / 'state.tmp';temp.write_text(json.dumps(state, indent=2));temp.replace(output / 'state.json')
    save()
    try:
        for direction in DIRECTIONS:
            item = plan[direction]
            # Recheck after earlier jobs: never silently consume changed inputs.
            if validate_cache(item['conditioning'])['files'] != item['inputFiles']:
                raise ValueError(f'Conditioning changed after validation: {direction}')
            if direction in completed:
                continue
            if stop_requested is not None and stop_requested():
                state['status'] = 'paused';state['finished'] = time.time();save()
                return 'paused'
            state['active'] = direction;save()
            command = [sys.executable, str(Path(__file__).with_name('generate.py')),
                       '--conditioning', item['conditioning'], '--runtime', str(runtime),
                       '--output', str(output / direction), '--seed', str(item['seed']), '--prompt', item['prompt']]
            with (output / f'{direction}.log').open('w') as log:
                if resident:
                    with redirect_stdout(log), redirect_stderr(log):
                        generate(item['conditioning'], runtime, output / direction,
                                 seed=item['seed'], prompt=item['prompt'], pipe_cache=pipe_cache)
                else:
                    (runner or subprocess.run)(command, check=True, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            verify_result(output / direction)
            state['completed'].append(direction);state['active'] = None;save()
        state['status'] = 'complete';state['finished'] = time.time();save()
        return 'complete'
    except BaseException as exc:
        state['status'] = 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed'
        state['error'] = repr(exc);state['finished'] = time.time();save()
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--runtime', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--check', action='store_true', help='Validate all input hashes without starting any generation')
    p.add_argument('--resume', action='store_true', help='Reuse verified complete directions; refuse partial jobs')
    p.add_argument('--resident', action='store_true', help='Experimental: retain one model across directions')
    a = p.parse_args()
    try:
        plan = validate_plan(a.plan)
        if a.check:
            print('Validated all 8 direction caches; no generation started')
            return
        if a.runtime is None or a.output is None:
            p.error('--runtime and --output are required unless --check is used')
        stopped = []
        def request_stop(signum, frame):
            if not stopped:
                stopped.append(signum)
                print('Stopping after the current direction finishes. Keep this terminal open.', file=sys.__stderr__, flush=True)
        previous = {sig: signal.signal(sig, request_stop) for sig in [signal.SIGINT, signal.SIGTERM]}
        try:
            result = run_plan(plan, a.runtime, a.output, resident=a.resident, resume=a.resume,
                              stop_requested=lambda: bool(stopped))
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        if result == 'paused':
            print('Paused. Repeat the same command with --resume to continue.', flush=True)
            p.exit(128 + stopped[0])
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        p.exit(2, f'Batch failed: {exc}\n')

if __name__ == '__main__':
    main()
