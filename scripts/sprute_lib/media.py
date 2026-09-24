"""Image/sequence operations shared by the native CLI. No inference imports."""
from pathlib import Path
import json
from PIL import Image, ImageOps

ORDER = ('S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW')
GRID = ('NW', 'N', 'NE', 'W', None, 'E', 'SW', 'S', 'SE')

def read_frames(path):
    path = Path(path)
    if path.is_dir():
        result = []
        for frame_path in sorted(path.glob('*.png')):
            with Image.open(frame_path) as im:
                result.append(im.convert('RGBA'))
        return result
    if path.suffix.lower() in ('.webp', '.gif', '.png'):
        result = []
        with Image.open(path) as im:
            for i in range(getattr(im, 'n_frames', 1)):
                im.seek(i)
                result.append(im.convert('RGBA'))
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
        if tile.getchannel('A').getextrema()[1] < 128:
            raise ValueError(f'Standing strip {direction} has no foreground pixels for its mask')
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

def narrow_grid(image, cell_width):
    """Remove equal side margins from each tile, without rescaling characters."""
    if cell_width is None:
        return image
    cell = image.width // 3
    left = (cell-cell_width)//2
    result = Image.new('RGBA', (cell_width*3, image.height))
    for i, direction in enumerate(GRID):
        x, y = i % 3, i // 3
        tile = image.crop((x*cell, y*cell, (x+1)*cell, (y+1)*cell))
        bounds = tile.getchannel('A').getbbox()
        if direction and bounds and (bounds[0] < left or bounds[2] > left+cell_width):
            raise ValueError(f'--cell-width {cell_width} would clip {direction}; use a wider cell')
        result.paste(tile.crop((left, 0, left+cell_width, cell)), (x*cell_width, y*cell))
    return result


def validate_animation_request(manifest_path, states, size, cell_width=None):
    if size <= 0 or size % 96:
        raise ValueError('Grid resolution must divide by 32 (SCAIL) and 3 (equal cells), e.g. 480 or 768')
    if cell_width is not None and (cell_width <= 0 or cell_width % 32 or cell_width > size//3):
        raise ValueError('--cell-width must be a positive multiple of 32, no wider than --size / 3')
    manifest_path = Path(manifest_path).resolve(strict=True)
    if not manifest_path.is_file():
        raise ValueError(f'Expected an input file, got a directory: {manifest_path}')
    manifest = json.loads(manifest_path.read_text())
    if len(states) != len(set(states)) or not states:
        raise ValueError('Choose distinct states')
    segments = {s['state']: s for s in manifest['segments']}
    for state in states:
        if state not in segments:
            raise ValueError(f'Unknown state: {state!r}; choose from {", ".join(segments)}')
        segment = segments[state]
        if not 0 <= segment['start_frame'] < segment['end_frame_exclusive'] <= manifest['frames']:
            raise ValueError('Invalid driver segment bounds')
    return manifest


def prepare_animation(standing, driver, manifest_path, states, out, size=768, replacement=False, cell_width=None):
    manifest = validate_animation_request(manifest_path, states, size, cell_width)
    source = read_frames(driver)
    if len(source) != manifest['frames']:
        raise ValueError(f'Driver has {len(source)} frames, manifest says {manifest["frames"]}')
    segments = {s['state']: s for s in manifest['segments']}
    selected, boundaries = [], []
    for state in states:
        s = segments[state]
        a, b = s['start_frame'], s['end_frame_exclusive']
        start = len(selected)
        selected.extend(source[a:b])
        boundaries.append(dict(state=state, start=start, count=b-a))
    out = Path(out)
    ref = narrow_grid(reference_grid(standing, size), cell_width)
    rgb, masks = [], []
    for frame in selected:
        frame = narrow_grid(frame.resize((size, size), Image.Resampling.LANCZOS), cell_width)
        rgb.append(gray(frame))
        mask = colored_mask(frame, replacement)
        # Decorative arrows are not a ninth character.
        fill = 'white' if replacement else 'black'
        width = frame.width
        mask.paste(fill, (width//3, size//3, 2*width//3, 2*size//3))
        masks.append(mask)
    # Wan's temporal VAE needs 4n+1. Pad only the tail, never truncate a state.
    n = len(rgb)
    padded = ((n-1+3)//4)*4+1
    rgb.extend([rgb[-1]]*(padded-n))
    masks.extend([masks[-1]]*(padded-n))
    out.mkdir(parents=True, exist_ok=True)
    gray(ref).save(out/'reference.png')
    colored_mask(ref, replacement, reference=True).save(out/'reference-mask.png')
    save_frames(rgb, out/'driver')
    save_frames(masks, out/'driver-mask')
    record = dict(fps=manifest['fps'], frames=n, inference_frames=padded,
                  size=size, segments=boundaries, replacement=replacement,
                  grid=list(GRID), order=list(ORDER))
    if cell_width is not None:
        record.update(width=cell_width*3, height=size, cell_width=cell_width)
    (out/'segments.json').write_text(json.dumps(record, indent=2))
    return record

def cut_grid(frames):
    out = {d: [] for d in ORDER}
    for frame in frames:
        w, h = frame.size
        if w % 3 or h % 3:
            raise ValueError(f'Grid dimensions must divide into 3 equal rows and columns, got {w}x{h}')
        w, h = w // 3, h // 3
        for i, d in enumerate(GRID):
            if d is not None:
                x, y = i % 3, i // 3
                out[d].append(frame.crop((x*w, y*h, (x+1)*w, (y+1)*h)))
    return out
