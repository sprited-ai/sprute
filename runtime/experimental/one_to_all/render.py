"""Render the evaluated 512px/65-frame conditioning profile without loading a model."""
import argparse
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess

import cv2
import matplotlib
import numpy as np
from PIL import Image
from head_policy import reference_head

PINNED = {
    'infer_function.py': '9c4f4d91b948fc6092432179e0cb97401f020b5e17819c0c66cdb576c6523e24',
    'draw_utils.py': '746424362dbdca1dbfac6ef3c3bedcd2a992ee2504d485131aa9e0b7dcb1e1d9',
}
NAMES = {'aaposemeta_to_dwpose', 'get_stickwidth', 'alpha_blend_color',
         'draw_bodypose_aligned', 'draw_handpose_aligned',
         'draw_facepose_aligned', 'draw_pose_aligned'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(fitted, reference_image, upstream, output, ffmpeg='ffmpeg'):
    fitted, reference_image, upstream, output = map(Path, (fitted, reference_image, upstream, output))
    data = json.loads(fitted.read_text())
    policy = data['visibility']
    if policy not in ('reference-head', 'hidden-head') or len(data['rows']) != 65:
        raise ValueError('Expected explicit head policy and exactly 65 frames')
    for meta in [data['reference'], *data['rows']]:
        for key, shape in [('keypoints_body', (20, 3)), ('keypoints_face', (69, 3)),
                           ('keypoints_left_hand', (21, 3)), ('keypoints_right_hand', (21, 3))]:
            value = np.asarray(meta[key], dtype=float)
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError(f'Invalid {key}')
    if policy == 'hidden-head':
        for meta in [data['reference'], *data['rows']]:
            if (np.any(np.asarray(meta['keypoints_body'])[[0, 14, 15, 16, 17], 2] != 0)
                    or np.any(np.asarray(meta['keypoints_face'])[:, 2] != 0)):
                raise ValueError('Hidden-head metadata must have unavailable head/face landmarks')
    with Image.open(reference_image) as source:
        image = source.convert('RGB')
    if image.size != (512, 512):
        raise ValueError('This evaluated profile requires a 512x512 reference')
    scope = dict(np=np, cv2=cv2, matplotlib=matplotlib, math=math, random=random, copy=copy)
    for filename, expected in PINNED.items():
        path = upstream / filename
        if sha(path) != expected:
            raise ValueError(f'Unsupported upstream source: {filename}')
        tree = ast.parse(path.read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.Assign) and
                 any(isinstance(t, ast.Name) and t.id == 'eps' for t in n.targets)]
        nodes += [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in NAMES]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), scope)
    subprocess.run([ffmpeg, '-version'], check=True, stdout=subprocess.DEVNULL)
    def pose(meta):
        return scope['aaposemeta_to_dwpose']({k: np.array(v) if k.startswith('keypoints_') else v for k, v in meta.items()})
    ref = pose(data['reference'])
    rows = [pose(m) for m in data['rows']]
    if policy == 'reference-head':
        rows = reference_head(ref, rows)
    output.mkdir(exist_ok=False)
    cache = output / 'cache'
    cache.mkdir()
    image.save(cache / 'image_input.png')
    Image.new('RGB', (512, 512), (0, 0, 0)).save(cache / 'mask_input.png')
    draw = scope['draw_pose_aligned']
    Image.fromarray(draw(ref, 512, 512, without_face=True)).save(cache / 'pose_input.png')
    frames = cache / 'frames'
    frames.mkdir()
    for i, p in enumerate(rows):
        im = draw(p, 512, 512, without_face=policy == 'hidden-head', head_change=False, face_change=True)
        if im.shape != (512, 512, 3) or not np.isfinite(im).all():
            raise ValueError('Invalid rendered frame')
        Image.fromarray(im).save(frames / f'{i+1:06d}.png')
    subprocess.run([ffmpeg, '-v', 'error', '-n', '-framerate', '24', '-i', str(frames / '%06d.png'),
                    '-frames:v', '65', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', str(cache / 'pose.mp4')], check=True)
    receipt = {'frames': 65, 'fps': 24, 'mode': 'ref', 'doAlign': False, 'headPolicy': policy,
               'fittedSha256': sha(fitted), 'referenceSha256': sha(reference_image), 'upstreamHashes': PINNED,
               'files': {str(p.relative_to(cache)): sha(p) for p in cache.rglob('*') if p.is_file()}}
    if len(receipt['files']) != 69:
        raise ValueError('Incomplete conditioning cache')
    (output / 'conditioning.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fitted', type=Path, required=True)
    p.add_argument('--reference-image', type=Path, required=True)
    p.add_argument('--upstream', type=Path, required=True, help='Directory containing the pinned two renderer source files')
    p.add_argument('--output', type=Path, required=True, help='New directory; partial failures are retained for inspection')
    p.add_argument('--ffmpeg', default='ffmpeg')
    a = p.parse_args()
    try:
        render(a.fitted, a.reference_image, a.upstream, a.output, a.ffmpeg)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        p.exit(2, f'Rendering failed: {exc}\n')
    print(f'Rendered 65 frames: {a.output / "cache"}')


if __name__ == '__main__':
    main()
