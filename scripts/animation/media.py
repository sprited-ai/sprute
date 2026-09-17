"""Image-only operations shared by the standalone experiment scripts."""
from fractions import Fraction
from pathlib import Path
import statistics
import subprocess
from PIL import Image, ImageChops, ImageStat
from common import read, write

ORDER = ['S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW']
GRID = {'NW': (0, 0), 'N': (1, 0), 'NE': (2, 0), 'W': (0, 1),
        'E': (2, 1), 'SW': (0, 2), 'S': (1, 2), 'SE': (2, 2)}


def bounds(size):
    return [round(i * size / 3) for i in range(4)]


def timings(count, fps, start=0):
    fps = Fraction(str(fps))
    if fps <= 0 or fps > 100:
        raise ValueError('FPS must be >0 and <=100')
    return [round(Fraction((i + 1) * 1000, 1) / fps) - round(Fraction(i * 1000, 1) / fps)
            for i in range(start, start + count)]


def save_webp(path, frames, durations, quality=65):
    if not frames or len(frames) != len(durations):
        raise ValueError('Frames and durations must be nonempty and match')
    if any(f.size != frames[0].size for f in frames):
        raise ValueError('Frame dimensions must match')
    if any(d <= 0 for d in durations):
        raise ValueError('Frame durations must be positive')
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations,
                   loop=0, lossless=False, quality=quality, method=4)
    total = 0
    with Image.open(path) as im:
        for n in range(im.n_frames):
            im.seek(n); im.load(); total += im.info.get('duration', sum(durations))
        # Identical frames may be coalesced by libwebp; duration is the invariant.
        if total != sum(durations) or im.size != frames[0].size:
            raise RuntimeError('Encoded WebP timing/size mismatch')


def compose_reference(sheet, output):
    with Image.open(sheet) as src:
        im = src.convert('RGBA')
    if im.width % 8:
        raise ValueError('Standing sheet must contain 8 equal-width horizontal cells')
    cw, ch = im.width // 8, im.height
    # Preserve original per-cell aspect; no bbox cropping or per-view rescaling.
    side = max(cw, ch)
    out = Image.new('RGBA', (side * 3, side * 3), '#808080')
    xoff, yoff = (side - cw) // 2, (side - ch) // 2
    for i, d in enumerate(ORDER):
        x, y = GRID[d]
        out.alpha_composite(im.crop((i * cw, 0, (i + 1) * cw, ch)),
                            (x * side + xoff, y * side + yoff))
    out.convert('RGB').save(output)
    return {'cell_width': cw, 'cell_height': ch, 'grid_cell': side,
            'padding': [xoff, yoff], 'direction_order': ORDER}


def decode_and_crop(video, folder):
    import json
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    # Decode every source frame; disable ffmpeg frame duplication/dropping.
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time',
        '-show_frames', '-of', 'json', str(video)]))
    stream = probe['streams'][0]
    width, height = stream['width'], stream['height']
    if width != height or width < 3:
        raise ValueError('Expected a square 3x3 grid video')
    fps = Fraction(stream['avg_frame_rate'])
    stamps = [float(f['best_effort_timestamp_time']) for f in probe['frames'] if 'best_effort_timestamp_time' in f]
    if len(stamps) < 2 or any(abs((b-a) - 1/float(fps)) > 0.002 for a, b in zip(stamps, stamps[1:])):
        raise ValueError('Expected constant frame rate video; normalize VFR explicitly first')
    decoded = folder / 'decoded'; decoded.mkdir(exist_ok=True)
    for old in decoded.glob('*.png'):
        old.unlink()
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(video), '-fps_mode', 'passthrough',
                    str(decoded / '%06d.png')], check=True)
    paths = sorted(decoded.glob('*.png'))
    if len(paths) != len(stamps):
        raise RuntimeError('Decoded frame count differs from probe')
    edge = bounds(width); result = {}
    for d, (x, y) in GRID.items():
        out = folder / 'cropped' / d; out.mkdir(parents=True, exist_ok=True)
        result[d] = []
        for i, p in enumerate(paths):
            with Image.open(p) as im:
                crop = im.crop((edge[x], edge[y], edge[x+1], edge[y+1]))
            dest = out / f'{i:04}.png'; crop.save(dest); result[d].append(dest)
    metadata = {'width': width, 'height': height, 'frames': len(paths), 'fps': str(fps),
                'durations_ms': timings(len(paths), fps), 'grid_edges': edge}
    write(folder / 'video.json', metadata)
    return result, metadata


def choose_loop(frames, low, high):
    """Estimate recurrence, then compare a window on both sides of the seam.

    This reports a candidate, not a guarantee of temporal/anatomical correctness.
    Bounds must describe a FULL gait period, to avoid selecting a half-stride.
    """
    if low < 3 or high < low or high >= len(frames) - 6:
        raise ValueError('Need period bounds >=3 and at least max_period+7 input frames')
    tiny = []
    for frame in frames:
        bg = Image.new('RGBA', frame.size, '#808080'); bg.alpha_composite(frame)
        tiny.append(bg.convert('RGB').resize((192, 192), Image.Resampling.BILINEAR))
    def diff(a, b):
        return sum(ImageStat.Stat(ImageChops.difference(tiny[a], tiny[b])).mean) / 3
    window = min(60, len(frames) - high)
    scores = [(sum(diff(i, i+lag) for i in range(window))/window, lag) for lag in range(low, high+1)]
    _, period = min(scores)
    seam, start = min((sum(diff(s+k, s+period+k) for k in range(-2, 3))/5, s)
                      for s in range(2, len(frames)-period-2))
    return {'start': start, 'end': start+period, 'period': period, 'seam_score': seam,
            'period_scores': [{'period': lag, 'score': score} for score, lag in sorted(scores)],
            'review_required': True}


def grids(sources, width):
    edge = bounds(width); count = len(next(iter(sources.values())))
    if set(sources) != set(GRID) or any(len(p) != count for p in sources.values()):
        raise ValueError('Need eight directions with equal frame counts')
    result = []
    for n in range(count):
        grid = Image.new('RGBA', (width, width))
        for d, (x, y) in GRID.items():
            with Image.open(sources[d][n]) as im:
                grid.alpha_composite(im.convert('RGBA'), (edge[x], edge[y]))
        result.append(grid)
    return result


def horizontal(grid_frames, sheet, register=False):
    """Invert reference padding. Optional single fixed transform per direction.

    Registration aligns median alpha height + horizontal center + foot baseline to
    the still. It is a heuristic and may overcorrect poses with large limb motion.
    """
    still = Image.open(sheet).convert('RGBA')
    cw, ch = still.width // 8, still.height
    if still.width % 8:
        raise ValueError('Invalid standing sheet')
    side = max(cw, ch); ox, oy = (side-cw)//2, (side-ch)//2
    per_direction = {d: [] for d in ORDER}
    for grid in grid_frames:
        restored = grid.resize((side*3, side*3), Image.Resampling.LANCZOS)
        for d, (x,y) in GRID.items():
            # Retain square until after registration, avoiding pre-cropping limbs.
            per_direction[d].append(restored.crop((x*side,y*side,(x+1)*side,(y+1)*side)))
    transforms = {}; clipped = 0
    def box(im):
        return im.getchannel('A').point(lambda a: 255 if a > 127 else 0).getbbox()
    for i, d in enumerate(ORDER):
        target = box(still.crop((i*cw,0,(i+1)*cw,ch)))
        boxes = [box(im) for im in per_direction[d]]
        if target is None or any(b is None for b in boxes):
            raise ValueError(f'Empty foreground in {d}')
        scale = 1.0; tx = -ox; ty = -oy
        if register:
            scale = (target[3]-target[1]) / statistics.median(b[3]-b[1] for b in boxes)
            tx = (target[0]+target[2])/2 - scale*statistics.median((b[0]+b[2])/2 for b in boxes)
            ty = target[3] - scale*statistics.median(b[3] for b in boxes)
        transforms[d] = {'scale': scale, 'translation': [tx, ty]}
        updated = []
        for im in per_direction[d]:
            b = box(im)
            if b[0]*scale+tx < 0 or b[2]*scale+tx > cw or b[1]*scale+ty < 0 or b[3]*scale+ty > ch:
                clipped += 1
            updated.append(im.transform((cw,ch), Image.Transform.AFFINE,
                (1/scale,0,-tx/scale,0,1/scale,-ty/scale), Image.Resampling.BICUBIC))
        per_direction[d] = updated
    if clipped:
        raise ValueError(f'{clipped} cells would clip foreground. Change registration or input layout; no silent clipping.')
    result = []
    for n in range(len(grid_frames)):
        row = Image.new('RGBA',(cw*8,ch))
        for i,d in enumerate(ORDER): row.alpha_composite(per_direction[d][n],(i*cw,0))
        result.append(row)
    return result, {'cell': [cw,ch], 'extra_gap': 0, 'registration': register, 'transforms': transforms}
