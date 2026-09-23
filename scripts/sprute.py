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

import sprute_models as models
from sprute_media import prepare_animation

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent/'workflows/assets'
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


def record_file(path):
    path = Path(path).resolve(strict=True)
    if path.is_dir():
        files = sorted(path.glob('*.png'))
        if not files:
            raise ValueError(f'No PNG frames in {path}')
        return [record_file(p) for p in files]
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def run_worker(args, stage, out, **settings):
    out = Path(out).resolve()
    job = dict(stage=stage, models=str(args.models.resolve()), out=str(out), **settings)
    # Record actual source/model locations as well as settings. Linking a new model invalidates resume.
    key = 'matte' if stage == 'export' else stage
    job['model_paths'] = {n: str((args.models/n).resolve()) for n in models.STAGES[key]}
    job['source_revisions'] = models.SOURCES
    job['implementation_sha256'] = {
        name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
        for name in ('sprute_inference.py', 'sprute_media.py', 'sprute_attention.py', 'sprute_loading.py', 'sprute_fp8.py')}
    for name in ('template', 'image', 'video', 'segments'):
        if name in job:
            job[name] = str(Path(job[name]).resolve(strict=True))
            job[name+'_record'] = record_file(job[name])
    if 'prepared' in job:
        job['prepared'] = str(Path(job['prepared']).resolve(strict=True))
        job['prepared_record'] = {p.name: record_file(p) for p in sorted(Path(job['prepared']).iterdir())}
    job = json.loads(json.dumps(job))
    dest = out/'job.json'
    if out.exists() and any(out.iterdir()):
        if not getattr(args, 'resume', False):
            raise FileExistsError(f'{out} is not empty; use a new --out or --resume')
        if not dest.exists() or json.loads(dest.read_text()) != job:
            raise ValueError(f'{out}: settings/inputs changed; use a new output directory')
        if (out/'complete.json').exists():
            expected = {'generate': 'reference.png', 'turntable': 'standing.png',
                        'animate': 'frames/00000.png', 'export': 'animation.json'}[stage]
            if not (out/expected).exists():
                raise FileNotFoundError(f'Completion marker exists but {expected} is missing; use a new --out')
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
    subprocess.run([sys.executable, str(HERE/'sprute_inference.py'), str(dest)], check=True, env=env)
    (out/'complete.json').write_text(json.dumps(dict(completed=datetime.now(timezone.utc).isoformat())))
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
    output = args.out.resolve()
    # Bind prepared artifacts to inputs; never silently reuse masks from another standing strip.
    prepared = output/'prepared'
    preparation = dict(standing=record_file(args.standing), driver=record_file(args.driver),
        manifest=record_file(args.manifest), states=states, size=args.size, replacement=args.replace)
    lock = output/'inputs.json'
    if output.exists() and any(output.iterdir()):
        if not args.resume or not lock.exists() or json.loads(lock.read_text()) != preparation:
            raise ValueError('Animation output already exists or inputs changed; choose a new --out')
    output.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(preparation, indent=2))
    if not (prepared/'segments.json').exists():
        prepare_animation(args.standing, args.driver, args.manifest, states,
                          prepared, args.size, args.replace)
    if args.prepare_only:
        print(prepared)
        return
    run_worker(args, 'animate', output/'inference', prepared=str(prepared),
               prompt=args.prompt, steps=args.steps, seed=args.seed)
    if not args.dry_run:
        run_worker(args, 'export', output/'animations', video=str(output/'inference/frames'),
                   segments=str(prepared/'segments.json'), quality=args.quality)


def run(args):
    """One command, still separate processes and resumable stage directories."""
    needed = ['turntable', 'animate'] + ([] if args.image else ['generate'])
    for stage in needed:
        models.require(args.models, stage)
    if args.dry_run:
        print(json.dumps(dict(stages=needed, out=str(args.out.resolve()),
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
        a.add_argument('--states', default='idle,walk,run')
        a.add_argument('--driver', type=Path, default=ASSETS/'sprute-v2-idle-walk-run-center-arrows.webp')
        a.add_argument('--manifest', type=Path, default=ASSETS/'sprute-v2-idle-walk-run-center-arrows.json')
        a.add_argument('--size', type=int, default=768)
        a.add_argument('--steps', type=int, default=8)
        a.add_argument('--replace', action='store_true', help='Replacement mode; default animation mode')
        a.add_argument('--quality', type=int, choices=range(1, 101), default=90, metavar='1..100')
    a = execution('animate', 'Standing strip -> SCAIL2 states -> direction WebPs')
    a.add_argument('--standing', type=Path, required=True)
    motion_options(a)
    a.add_argument('--prompt', default='')
    a.add_argument('--prepare-only', action='store_true', help='Build driver/reference/masks without GPU or weights')
    r = execution('run', 'End-to-end: prompt/reference -> standing -> idle/walk/run')
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
            from sprute_inference import import_wan
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
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'sprute: {exc}', file=sys.stderr)
        sys.exit(1)
