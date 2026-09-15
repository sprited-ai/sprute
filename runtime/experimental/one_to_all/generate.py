"""Run one experimental 65-frame walk on an already configured One-to-All runtime."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback
from short_clip import split_plan

INFERENCE_SHA256 = '22a20ba014ecbe920da08d44b9311ec8e280a9b3d8e102bed61b59523cc5b8f9'

def runtime_environment():
    """Record loaded module origins rather than assuming a particular overlay."""
    packages = {}
    for name in ['torch', 'numpy', 'transformers', 'tokenizers', 'huggingface_hub',
                 'diffusers', 'accelerate', 'decord', 'PIL', 'imageio',
                 'imageio_ffmpeg', 'safetensors', 'einops']:
        module = sys.modules.get(name)
        if module is not None:
            packages[name] = {'version': getattr(module, '__version__', None),
                              'path': getattr(module, '__file__', None)}
    return {'pythonExecutable': sys.executable, 'pythonVersion': sys.version,
            'prefix': sys.prefix, 'basePrefix': sys.base_prefix,
            'moduleSearchPath': list(sys.path), 'loadedPackages': packages}

def validate_cache(conditioning):
    conditioning = Path(conditioning).resolve()
    cache = conditioning / 'cache'
    metadata = json.loads((conditioning / 'conditioning.json').read_text())
    expected = {'image_input.png', 'pose_input.png', 'mask_input.png', 'pose.mp4'}
    expected.update(f'frames/{i:06d}.png' for i in range(1, 66))
    if set(metadata['files']) != expected or metadata['frames'] != 65 or metadata['fps'] != 24:
        raise ValueError('Expected the complete 65-frame / 24fps cache manifest')
    for name, digest in metadata['files'].items():
        path = (cache / name).resolve()
        if not path.is_relative_to(cache.resolve()):
            raise ValueError('Cache file escapes its directory')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Input hash mismatch: {name}')
    return metadata


def generate(conditioning, runtime, output, *, seed=42, prompt='', pipe_cache=None):
    conditioning = Path(conditioning).resolve()
    RUNTIME = Path(runtime).resolve()
    HERE = Path(output).absolute()
    CODE = RUNTIME / 'code/video-generation'
    CACHE = conditioning / 'cache'
    OUT = HERE / 'output'
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError('Seed must be an unsigned 32-bit integer')
    validate_cache(conditioning)
    if hashlib.sha256((CODE / 'inference_1.3b.py').read_bytes()).hexdigest() != INFERENCE_SHA256:
        raise ValueError('Unsupported upstream inference source')
    for folder in ['models/base', 'models/base/vae', 'models/checkpoint']:
        if not (RUNTIME / folder).is_dir():
            raise ValueError(f'Missing configured runtime folder: {folder}')
    HERE.mkdir(exist_ok=False)  # exclusive job claim; never reuse or automatically retry
    OUT.mkdir()
    state = {'status': 'preflight', 'pid': os.getpid(), 'started': time.time()}
    def save(**updates):
        state.update(updates)
        tmp = HERE / 'state.tmp'
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(HERE / 'state.json')
        print(json.dumps(updates), flush=True)
    try:
        save()
        metadata = json.loads((conditioning / 'conditioning.json').read_text())
        for name, digest in metadata['files'].items():
            assert hashlib.sha256((CACHE / name).read_bytes()).hexdigest() == digest, name
        os.chdir(CODE)
        sys.path.insert(0, str(CODE))
        spec = importlib.util.spec_from_file_location('upstream_trial', CODE / 'inference_1.3b.py')
        upstream = importlib.util.module_from_spec(spec)
        source = (CODE / 'inference_1.3b.py').read_text()
        if source.count('manual_seed(42)') != 1:
            raise ValueError('Unsupported seed injection point')
        source = source.replace('manual_seed(42)', f'manual_seed({seed})')
        (HERE / 'effective-inference.py').write_text(source)
        exec(compile(source, str(CODE / 'inference_1.3b.py'), 'exec'), upstream.__dict__)
        upstream.model_path = str(RUNTIME / 'models/base')
        upstream.vae_path = str(RUNTIME / 'models/base/vae')
        upstream.output_base_dir = str(OUT)
        original_plan = upstream.build_split_plan
        upstream.build_split_plan = lambda n: split_plan(n, original_plan)
        assert upstream.build_split_plan(65) == [(0, 65)]
        original_build = upstream.build_pipe
        timings = {}
        def build(device, checkpoint):
            save(status='loading-model', device=device)
            cuda = upstream.torch.cuda
            cuda.synchronize(device)
            cuda.reset_peak_memory_stats(device)
            properties = cuda.get_device_properties(device)
            memory = {'device': properties.name, 'totalBytes': properties.total_memory,
                      'torchVersion': upstream.torch.__version__,
                      'cudaVersion': upstream.torch.version.cuda}
            def snapshot():
                return {'allocatedBytes': cuda.memory_allocated(device),
                        'reservedBytes': cuda.memory_reserved(device),
                        'peakAllocatedBytes': cuda.max_memory_allocated(device),
                        'peakReservedBytes': cuda.max_memory_reserved(device)}
            started = time.perf_counter()
            cache_key = (str(RUNTIME), INFERENCE_SHA256, device, str(checkpoint))
            reused = pipe_cache is not None and cache_key in pipe_cache
            pipe = pipe_cache[cache_key] if reused else original_build(device, checkpoint)
            if pipe_cache is not None and not reused:
                pipe_cache[cache_key] = pipe
            # CUDA work is asynchronous; measure completion, not just dispatch.
            upstream.torch.cuda.synchronize(device)
            timings['modelLoadSeconds'] = time.perf_counter() - started
            timings['modelReused'] = reused
            memory['afterLoad'] = snapshot()
            save(status='generating', strictCheckpointLoaded=True)
            class TimedPipe:
                def __call__(self, *args, **kwargs):
                    upstream.torch.cuda.synchronize(device)
                    started = time.perf_counter()
                    result = pipe(*args, **kwargs)
                    upstream.torch.cuda.synchronize(device)
                    timings.setdefault('pipelineCallsSeconds', []).append(time.perf_counter() - started)
                    memory.setdefault('afterPipelineCalls', []).append(snapshot())
                    (HERE / 'memory.json').write_text(json.dumps(memory, indent=2))
                    return result
            return TimedPipe()
        upstream.build_pipe = build
        manifest = {
            'upstreamCommit': 'b3c9d886c93c43e767b995e93968708ee2d410cb',
            'inferenceSha256': hashlib.sha256((CODE / 'inference_1.3b.py').read_bytes()).hexdigest(),
            'inputFiles': metadata['files'], 'frames': 65, 'width': 384, 'height': 384,
            'fps': 24, 'seed': seed, 'steps': 30, 'imageCFG': 2.5, 'poseCFG': 1.5,
            'prompt': prompt, 'mode': 'ref', 'doAlign': False, 'poseSource': 'provided conditioning cache',
            'shortClipAdapter': '277, one chunk [0,65)',
            'runtimeDeviations': 'Narrowed package initializers; actual dependency environment recorded separately',
            'environment': runtime_environment(),
        }
        (HERE / 'run.json').write_text(json.dumps(manifest, indent=2))
        worker_started = time.perf_counter()
        upstream.unified_worker(0, 1, [('sprute-walk', str(CACHE), '', '', 2.5, 1.5, prompt)], str(RUNTIME / 'models/checkpoint'))
        timings['workerSeconds'] = time.perf_counter() - worker_started
        (HERE / 'timings.json').write_text(json.dumps(timings, indent=2))
        frames = sorted(OUT.rglob('frame_*.png'))
        assert len(frames) == 65, len(frames)
        from PIL import Image
        for frame in frames:
            with Image.open(frame) as im:
                assert im.size == (384, 384), (frame, im.size)
        hashes = {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()}
        (HERE / 'output-hashes.json').write_text(json.dumps(hashes, indent=2))
        save(status='complete', frames=len(frames), finished=time.time())
    except BaseException:
        save(status='failed', error=traceback.format_exc(), finished=time.time())
        raise

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--conditioning', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--prompt', default='')
    a = p.parse_args()
    try:
        generate(a.conditioning, a.runtime, a.output, seed=a.seed, prompt=a.prompt)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.exit(2, f'Generation failed: {exc}\n')

if __name__ == '__main__':
    main()
