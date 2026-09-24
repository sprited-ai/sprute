#!/usr/bin/env python3
"""Sprute's native CLI seed: explicit models, independent stages, portable outputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile

from sprute_lib import models
from sprute_lib.media import ORDER, prepare_animation, validate_animation_request

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent/'assets'
TURN_PROMPT = ('A 360-degree turning and circling video of a 2D RPG game character. '
    'Pixel Art. Game Sprite. Full-body long shot with a plain gray background. '
    'The character stands upright with arms resting beside the body and rotates in place '
    'through one full turn. Preserve the reference proportions, clothes, colors and hairstyle. '
    'Clear readable silhouette, clean contours, flat local colors with restrained cel shading. '
    'Fixed camera, constant character size, feet on the same spot. '
    'aesthetic score: 5.5. motion score: 3.0. There is no text in the video.')
NEGATIVE = ('3D, maya, render, blender, photorealistic, glossy plastic, sculpted figurine, '
    'dramatic lighting, gradients, walking, running, dancing, camera movement, zoom, '
    'cropped feet, outfit change, extra limbs, text, scene change, dithering')


def fingerprint_input(path):
    """Fingerprint a file or an ordered PNG sequence for resume validation."""
    path = Path(path).resolve(strict=True)
    if path.is_dir():
        files = sorted(path.glob('*.png'))
        if not files:
            raise ValueError(f'No PNG frames in {path}')
        return [fingerprint_input(p) for p in files]
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return dict(path=str(path), sha256=digest.hexdigest())


def verify_outputs(stage, out, job):
    """A completion marker alone is not proof that the usable outputs remain."""
    out = Path(out)
    if stage == 'generate':
        expected = ['reference.png']
    elif stage == 'turntable':
        expected = ['standing.png', 'turntable.webp', 'selection.json',
                    *[f'{d}.png' for d in ORDER]]
    elif stage == 'animate':
        info = json.loads((Path(job['prepared'])/'segments.json').read_text())
        expected = ['animation-rgb.webp', *[f'frames/{i:05d}.png' for i in range(info['frames'])]]
    else:
        info = json.loads(Path(job['segments']).read_text())
        expected = ['animation.json']
        for segment in info['segments']:
            state = segment['state']
            expected.extend(f'{state}/{d}.webp' for d in [*ORDER, 'horizontal'])
            expected.extend(f'{state}/{d}/{i:05d}.png'
                            for d in ORDER for i in range(segment['count']))
    for name in expected:
        path = out/name
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f'Output missing or empty: {path}; use a new --out')


def run_worker(args, stage, out, **settings):
    out = Path(out).resolve()
    job = dict(stage=stage, models=str(args.models.resolve()), out=str(out), **settings)
    if getattr(args, 'vram_limit_gib', None) is not None:
        job['vram_limit_gib'] = args.vram_limit_gib
    # Record actual source/model locations as well as settings. Linking a new model invalidates resume.
    key = 'matte' if stage == 'export' else stage
    job['model_paths'] = {n: str((args.models/n).resolve()) for n in models.STAGES[key]}
    job['source_revisions'] = models.SOURCES
    job['implementation_sha256'] = {
        name: hashlib.sha256((HERE/'sprute_lib'/name).read_bytes()).hexdigest()
        for name in ('inference.py', 'media.py', 'attention.py', 'loading.py', 'fp8.py', 'umt5.py')}
    for name in ('template', 'image', 'video', 'segments', 'text_encoder_fp8'):
        if job.get(name) is not None:
            job[name] = str(Path(job[name]).resolve(strict=True))
            job[name+'_record'] = fingerprint_input(job[name])
    if 'prepared' in job:
        job['prepared'] = str(Path(job['prepared']).resolve(strict=True))
        job['prepared_record'] = {p.name: fingerprint_input(p) for p in sorted(Path(job['prepared']).iterdir())}
    job = json.loads(json.dumps(job))
    dest = out/'job.json'
    if out.exists() and any(out.iterdir()):
        if not getattr(args, 'resume', False):
            raise FileExistsError(f'{out} is not empty; use a new --out or --resume')
        if not dest.exists() or json.loads(dest.read_text()) != job:
            raise ValueError(f'{out}: settings/inputs changed; use a new output directory')
        if (out/'complete.json').exists():
            verify_outputs(stage, out, job)
            print(f'Already complete: {out}')
            return out
    models.require(args.models, key)
    out.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(job, indent=2))
    if getattr(args, 'dry_run', False):
        print(json.dumps(job, indent=2))
        return out
    env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    # No shell interpolation; preserve prompts and paths verbatim.
    print(f'[{stage}] Starting', flush=True)
    subprocess.run([sys.executable, '-m', 'sprute_lib.inference', str(dest)],
                   cwd=HERE, check=True, env=env)
    verify_outputs(stage, out, job)
    (out/'complete.json').write_text(json.dumps(dict(completed=datetime.now(timezone.utc).isoformat())))
    print(f'[{stage}] Complete', flush=True)
    return out


def generate(args):
    return run_worker(args, 'generate', args.out, template=str(args.template),
        prompt=args.prompt, seed=args.seed, steps=args.steps, guidance=20,
        cell_index=args.cell_index)


def turntable(args):
    return run_worker(args, 'turntable', args.out, image=str(args.image), prompt=args.prompt,
        negative=NEGATIVE, seed=args.seed, steps=args.steps, size=args.size,
        precision=args.precision)


def animate(args):
    states = [s.strip() for s in args.states.split(',')]
    validate_animation_request(args.manifest, states, args.size, args.cell_width)
    output = args.out.resolve()
    # Bind prepared artifacts to inputs; never silently reuse masks from another standing strip.
    prepared = output/'prepared'
    preparation = dict(standing=fingerprint_input(args.standing), driver=fingerprint_input(args.driver),
        manifest=fingerprint_input(args.manifest), states=states, size=args.size, replacement=args.replace,
        inference_mode="per-state")
    if args.cell_width is not None:
        preparation['cell_width'] = args.cell_width
    lock = output/'inputs.json'
    if output.exists() and any(output.iterdir()):
        if not args.resume or not lock.exists() or json.loads(lock.read_text()) != preparation:
            raise ValueError('Animation output already exists or inputs changed; choose a new --out')
    output.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(preparation, indent=2))
    records = []
    for state in states:
        state_prepared = prepared/state
        if not (state_prepared/'segments.json').exists():
            prepare_animation(args.standing, args.driver, args.manifest, [state],
                              state_prepared, args.size, args.replace, args.cell_width)
        records.append(json.loads((state_prepared/'segments.json').read_text()))
    # Keep a combined export timeline, but never feed it to the diffusion model.
    info = {**records[0], 'frames': sum(r['frames'] for r in records),
            'inference_mode': 'per-state', 'segments': []}
    info.pop('inference_frames', None)
    offset = 0
    for state, record in zip(states, records):
        info['segments'].append(dict(state=state, start=offset, count=record['frames']))
        offset += record['frames']
    (prepared/'segments.json').write_text(json.dumps(info, indent=2))
    if args.prepare_only:
        print(prepared)
        return
    for state in states:
        run_worker(args, 'animate', output/'inference'/state, prepared=str(prepared/state),
                   prompt=args.prompt, steps=args.steps, seed=args.seed,
                   precision=args.precision,
                   text_encoder_fp8=str(args.text_encoder_fp8) if args.text_encoder_fp8 else None)
    if not args.dry_run:
        # Hard links provide export's ordered sequence without duplicating PNG data.
        frames = output/'inference/frames'
        frames.mkdir(parents=True, exist_ok=True)
        for segment in info['segments']:
            for i in range(segment['count']):
                source = output/'inference'/segment['state']/'frames'/f'{i:05d}.png'
                target = frames/f"{segment['start']+i:05d}.png"
                if target.exists():
                    if not target.samefile(source):
                        raise ValueError(f'{target}: unexpected frame; use a new --out')
                else:
                    os.link(source, target)
        run_worker(args, 'export', output/'animations', video=str(frames),
                   segments=str(prepared/'segments.json'), quality=args.quality)


def run(args):
    """Keep implementation artifacts outside the user's final output by default."""
    validate_animation_request(args.manifest, [s.strip() for s in args.states.split(',')], args.size, args.cell_width)
    if args.keep_intermediates or args.dry_run:
        return run_pipeline(args)
    if args.resume:
        raise ValueError('--resume requires --keep-intermediates; temporary runs do not retain checkpoints')
    output = args.out.resolve()
    if output.exists():
        raise FileExistsError(f'{output} already exists; choose a new --out')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Same filesystem permits publishing the completed directory with one rename.
    with tempfile.TemporaryDirectory(prefix='.sprute-', dir=output.parent) as temp:
        work = Path(temp)/'work'
        run_pipeline(argparse.Namespace(**{**vars(args), 'out': work}))
        final = Path(temp)/'final'
        final.mkdir()
        reference = Path(args.image) if args.image else work/'reference/reference.png'
        shutil.copy2(reference, final/'reference.png')
        shutil.copy2(work/'standing/standing.png', final/'standing.png')
        animations = work/'motion/animations'
        manifest = json.loads((animations/'animation.json').read_text())
        manifest['standing_selection'] = json.loads((work/'standing/selection.json').read_text())
        for segment in manifest['segments']:
            state = segment['state']
            (final/state).mkdir()
            for direction in [*ORDER, 'horizontal']:
                shutil.copy2(animations/state/f'{direction}.webp', final/state/f'{direction}.webp')
        manifest.update(seed=args.seed, prompt=args.prompt, turntable_size=args.turntable_size,
                        turntable_precision=args.turntable_precision, steps=args.steps,
                        turntable_prompt=args.turntable_prompt, animation_prompt='',
                        precision=args.precision, size=args.size, replacement=args.replace,
                        quality=args.quality, fill_steps=args.fill_steps,
                        vram_limit_gib=args.vram_limit_gib,
                        text_encoder_fp8=(str(args.text_encoder_fp8.resolve())
                                          if args.text_encoder_fp8 else None))
        (final/'manifest.json').write_text(json.dumps(manifest, indent=2))
        if output.exists():
            raise FileExistsError(f'{output} appeared during generation; refusing to replace it')
        final.rename(output)
    print(f'Saved character: {output}')


def run_pipeline(args):
    """Internal stages; also available persistently for debugging and resuming."""
    # Check later-stage input paths before spending GPU time on earlier stages.
    for path in (args.image or args.template, args.driver, args.manifest,
                 args.text_encoder_fp8):
        if path is not None:
            resolved = Path(path).resolve(strict=True)
            if not resolved.is_file():
                raise ValueError(f'Expected an input file, got a directory: {resolved}')
    needed = ([] if args.image else ['generate']) + ['turntable', 'animate']
    for stage in needed:
        models.require(args.models, stage)
    if args.dry_run:
        print(json.dumps(dict(stages=[*needed, 'export'], out=str(args.out.resolve()),
                              states=args.states, seed=args.seed), indent=2))
        return
    root = args.out.resolve()
    reference = args.image
    if reference is None:
        run_worker(args, 'generate', root/'reference', template=str(args.template),
                   prompt=args.prompt, seed=args.seed, steps=args.fill_steps,
                   guidance=20, cell_index=6)
        reference = root/'reference/reference.png'
    run_worker(args, 'turntable', root/'standing', image=str(reference),
               prompt=args.turntable_prompt, negative=NEGATIVE,
               seed=args.seed, steps=args.steps, size=args.turntable_size,
               precision=args.turntable_precision)
    animation_args = argparse.Namespace(**vars(args))
    animation_args.out = root/'motion'
    animation_args.standing = root/'standing/standing.png'
    animation_args.prompt = ''
    animation_args.prepare_only = False
    animate(animation_args)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--models', type=Path, default=models.DEFAULT_MODELS,
                   help='Model directory; defaults to sprute-2/models')
    sub = p.add_subparsers(dest='command', required=True)
    m = sub.add_parser('models', help='Explicit setup, download, or local symlinks')
    ms = m.add_subparsers(dest='action', required=True)
    ms.add_parser('setup', help='Fetch pinned official AniSora/SCAIL2 Python source')
    ms.add_parser('list')
    dl = ms.add_parser('download')
    dl.add_argument('--stage', choices=['all', *models.STAGES], required=True)
    lk = ms.add_parser('link')
    lk.add_argument('name', choices=list(models.MODELS))
    lk.add_argument('path', type=Path)
    doc = sub.add_parser('doctor', help='Check installed dependencies and model paths')
    doc.add_argument('--stage', choices=list(models.STAGES), default='animate')
    def execution(name, help):
        q = sub.add_parser(name, help=help)
        q.add_argument('--out', type=Path, required=True)
        q.add_argument('--seed', type=int, default=42)
        q.add_argument('--vram-limit-gib', type=float,
                       help='Limit each worker\'s PyTorch allocator; excludes other CUDA allocations')
        q.add_argument('--resume', action='store_true')
        q.add_argument('--dry-run', action='store_true', help='Validate and save job without loading weights')
        return q
    g = execution('generate', 'Prompt + masked SpriteDX template -> reference RGBA')
    g.add_argument('--template', type=Path, default=ASSETS/'sprute-v2-fill.png')
    g.add_argument('--prompt', default='pixelated retro pixel art cute NPC character')
    g.add_argument('--steps', type=int, default=50)
    g.add_argument('--cell-index', type=int, choices=range(8), default=6)
    t = execution('turntable', 'Reference RGBA -> AniSora rotation -> eight-view alpha strip')
    t.add_argument('--image', type=Path, required=True)
    t.add_argument('--prompt', default=TURN_PROMPT)
    t.add_argument('--steps', type=int, default=8)
    t.add_argument('--size', type=int, choices=[256, 512, 640, 768], default=256)
    t.add_argument('--precision', choices=['bf16', 'fp8'], default='bf16')
    def motion_options(a):
        a.add_argument('--precision', choices=['bf16', 'fp8'], default='bf16',
                       help='SCAIL2 linear-layer precision (FP8 is experimental)')
        a.add_argument('--text-encoder-fp8', type=Path,
                       help='Existing scaled-FP8 UMT5 checkpoint for SCAIL2')
        a.add_argument('--states', default='idle,walk,run')
        a.add_argument('--driver', type=Path, default=ASSETS/'sprute-v2-idle-walk-run-center-arrows.webp')
        a.add_argument('--manifest', type=Path, default=ASSETS/'sprute-v2-idle-walk-run-center-arrows.json')
        a.add_argument('--size', type=int, default=768)
        a.add_argument('--cell-width', type=int,
                       help='Tile width without rescaling (default: 192, capped at --size / 3)')
        a.add_argument('--steps', type=int, default=8)
        a.add_argument('--replace', action='store_true', help='Replacement mode; default animation mode')
        a.add_argument('--quality', type=int, choices=range(1, 101), default=90, metavar='1..100')
    a = execution('animate', 'Standing strip -> SCAIL2 states -> direction WebPs')
    a.add_argument('--standing', type=Path, required=True)
    motion_options(a)
    a.add_argument('--prompt', default='')
    a.add_argument('--prepare-only', action='store_true', help='Build driver/reference/masks without GPU or weights')
    r = execution('run', 'End-to-end: prompt/reference -> standing -> idle/walk/run')
    r.add_argument('--keep-intermediates', action='store_true',
                   help='Keep stage directories in --out for inspection and --resume')
    motion_options(r)
    r.add_argument('--image', type=Path, help='Already prepared full-body character; skips FLUX')
    r.add_argument('--prompt', default='pixelated retro pixel art cute NPC character')
    r.add_argument('--template', type=Path, default=ASSETS/'sprute-v2-fill.png')
    r.add_argument('--fill-steps', type=int, default=50)
    r.add_argument('--turntable-size', type=int, choices=[256, 512, 640, 768], default=256)
    r.add_argument('--turntable-precision', choices=['bf16', 'fp8'], default='bf16')
    r.add_argument('--turntable-prompt', default=TURN_PROMPT)
    e = execution('export', 'Existing grid frames/video -> ToonOut -> alpha animation states')
    e.add_argument('--video', type=Path, required=True)
    e.add_argument('--segments', type=Path, required=True)
    e.add_argument('--quality', type=int, choices=range(1, 101), default=90, metavar='1..100')
    return p


def main():
    args = parser().parse_args()
    args.models = args.models.expanduser().resolve()
    if getattr(args, 'vram_limit_gib', None) is not None and not 0 < args.vram_limit_gib < float('inf'):
        raise ValueError('--vram-limit-gib must be a finite positive number')
    if hasattr(args, 'cell_width') and args.cell_width is None:
        args.cell_width = min(192, args.size // 3)
    if hasattr(args, 'seed') and not 0 <= args.seed < 2**64:
        raise ValueError('--seed must be between 0 and 18446744073709551615; negative seeds randomize upstream stages independently')
    if hasattr(args, 'steps') and args.steps < 1:
        raise ValueError('--steps must be positive')
    if hasattr(args, 'fill_steps') and args.fill_steps < 1:
        raise ValueError('--fill-steps must be positive')
    if args.command == 'models':
        if args.action == 'setup':
            models.setup_sources(args.models)
        elif args.action == 'download':
            models.download(args.models, args.stage)
        elif args.action == 'link':
            print(models.link(args.models, args.name, args.path))
        else:
            for name in models.MODELS:
                path = args.models/name
                print(f'{name:15} {"OK" if path.exists() else "MISSING":7} {path.resolve()}')
    elif args.command == 'doctor':
        import importlib.util
        packages = ['torch', 'diffusers', 'transformers', 'safetensors', 'cv2', 'timm', 'einops']
        if args.stage == 'animate':
            packages.append('decord')
        missing = [x for x in packages if importlib.util.find_spec(x) is None]
        if missing:
            raise RuntimeError('Missing dependencies: '+', '.join(missing))
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA is unavailable; preprocessing works on CPU, inference needs CUDA')
        models.require(args.models, args.stage)
        if args.stage in ('animate', 'turntable'):
            from sprute_lib.inference import import_wan
            import_wan(args.models, 'scail2' if args.stage == 'animate' else 'anisora')
        print('Dependencies and model paths present. This is not an inference/parity test.')
    elif args.command == 'export':
        run_worker(args, 'export', args.out, video=str(args.video),
                   segments=str(args.segments), quality=args.quality)
    else:
        globals()[args.command](args)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('sprute: Interrupted.', file=sys.stderr)
        sys.exit(130)
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'sprute: {exc}', file=sys.stderr)
        sys.exit(1)
