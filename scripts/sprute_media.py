"""Image/sequence operations shared by the native CLI. No inference imports."""
from pathlib import Path
import json
from PIL import Image, ImageOps

ORDER = ('S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW')
GRID = ('NW', 'N', 'NE', 'W', None, 'E', 'SW', 'S', 'SE')

def read_frames(path):
    path = Path(path)
    if path.is_dir():
        return [Image.open(p).convert('RGBA') for p in sorted(path.glob('*.png'))]
    if path.suffix.lower() in ('.webp', '.gif', '.png'):
        im = Image.open(path)
        result = []
        for i in range(getattr(im, 'n_frames', 1)):
            im.seek(i)
            result.append(im.convert('RGBA').copy())
        return result
    import imageio.v3 as iio
    return [Image.fromarray(a).convert('RGBA') for a in iio.imiter(path)]

def save_frames(frames, path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        frame.save(path / f'{i:05d}.png')

def webp(frames, path, fps=24, quality=90):
    if not frames:
        raise ValueError('Cannot save an empty animation')
    durations = [round((i+1)*1000/fps)-round(i*1000/fps) for i in range(len(frames))]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, lossless=False, quality=quality, method=4)

def gray(image):
    rgba = image.convert('RGBA')
    bg = Image.new('RGBA', rgba.size, (128, 128, 128, 255))
    return Image.alpha_composite(bg, rgba).convert('RGB')

def pad(image, size):
    image = ImageOps.contain(image.convert('RGBA'), size, Image.Resampling.LANCZOS)
    result = Image.new('RGBA', size)
    result.alpha_composite(image, ((size[0]-image.width)//2, (size[1]-image.height)//2))
    return result

def strip(cells):
    if len(cells) != 8 or len({x.size for x in cells}) != 1:
        raise ValueError('Expected eight equally sized directional cells')
    w, h = cells[0].size
    out = Image.new('RGBA', (8*w, h))
    for i, im in enumerate(cells):
        out.alpha_composite(im.convert('RGBA'), (i*w, 0))
    return out

def reference_grid(path, size):
    im = Image.open(path).convert('RGBA')
    if im.width % 8:
        raise ValueError('Standing strip width must divide into 8 equal cells')
    if im.getchannel('A').getextrema()[0] == 255:
        raise ValueError('Standing strip must have transparency for character masks')
    cell = im.width // 8
    out = Image.new('RGBA', (size, size))
    for index, direction in enumerate(GRID):
        if direction is None:
            continue
        source = ORDER.index(direction)
        tile = im.crop((source*cell, 0, (source+1)*cell, im.height))
        x, y = index % 3, index // 3
        left, top, right, bottom = (round(x*size/3), round(y*size/3),
                                    round((x+1)*size/3), round((y+1)*size/3))
        out.alpha_composite(pad(tile, (right-left, bottom-top)), (left, top))
    return out

def colored_mask(rgba, replacement=False, reference=False):
    # Official SCAIL2 semantics: background visible=white, hidden=black.
    visible = (not replacement) if reference else replacement
    out = Image.new('RGB', rgba.size, 'white' if visible else 'black')
    alpha = rgba.convert('RGBA').getchannel('A').point(lambda x: 255 if x >= 128 else 0)
    out.paste((0, 0, 255), mask=alpha)
    return out

def prepare_animation(standing, driver, manifest_path, states, out, size=768, replacement=False):
    if size <= 0 or size % 96:
        raise ValueError('Grid resolution must divide by 32 (SCAIL) and 3 (equal cells), e.g. 480 or 768')
    manifest = json.loads(Path(manifest_path).read_text())
    source = read_frames(driver)
    if len(source) != manifest['frames']:
        raise ValueError(f'Driver has {len(source)} frames, manifest says {manifest["frames"]}')
    if len(states) != len(set(states)) or not states:
        raise ValueError('Choose distinct states')
    segments = {s['state']: s for s in manifest['segments']}
    selected, boundaries = [], []
    for state in states:
        if state not in segments:
            raise ValueError(f'Unknown state: {state}')
        s = segments[state]
        a, b = s['start_frame'], s['end_frame_exclusive']
        if not 0 <= a < b <= len(source):
            raise ValueError('Invalid driver segment bounds')
        start = len(selected)
        selected.extend(source[a:b])
        boundaries.append(dict(state=state, start=start, count=b-a))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ref = reference_grid(standing, size)
    gray(ref).save(out/'reference.png')
    colored_mask(ref, replacement, reference=True).save(out/'reference-mask.png')
    rgb, masks = [], []
    for frame in selected:
        frame = frame.resize((size, size), Image.Resampling.LANCZOS)
        rgb.append(gray(frame))
        mask = colored_mask(frame, replacement)
        # Decorative arrows are not a ninth character.
        fill = 'white' if replacement else 'black'
        mask.paste(fill, (round(size/3), round(size/3), round(2*size/3), round(2*size/3)))
        masks.append(mask)
    # Wan's temporal VAE needs 4n+1. Pad only the tail, never truncate a state.
    n = len(rgb)
    padded = ((n-1+3)//4)*4+1
    rgb.extend([rgb[-1]]*(padded-n))
    masks.extend([masks[-1]]*(padded-n))
    save_frames(rgb, out/'driver')
    save_frames(masks, out/'driver-mask')
    record = dict(fps=manifest['fps'], frames=n, inference_frames=padded,
                  size=size, segments=boundaries, replacement=replacement,
                  grid=list(GRID), order=list(ORDER))
    (out/'segments.json').write_text(json.dumps(record, indent=2))
    return record

def cut_grid(frames):
    out = {d: [] for d in ORDER}
    for frame in frames:
        w, h = frame.size
        for i, d in enumerate(GRID):
            if d is not None:
                x, y = i % 3, i // 3
                out[d].append(frame.crop((round(x*w/3), round(y*h/3),
                                         round((x+1)*w/3), round((y+1)*h/3))))
    return out
