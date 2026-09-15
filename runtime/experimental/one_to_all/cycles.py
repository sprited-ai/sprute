"""Copy an explicit batch frame range into Sprute's existing cycle format."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
from batch import DIRECTIONS, verify_result


def extract(batch, output, start, end):
    batch, output = Path(batch).resolve(), Path(output).absolute()
    state = json.loads((batch / 'state.json').read_text())
    if state['status'] != 'complete' or state['completed'] != DIRECTIONS:
        raise ValueError('Expected all eight completed directions')
    if any(isinstance(x, bool) or not isinstance(x, int) for x in [start, end]) or not 0 <= start < end < 65:
        raise ValueError('Select at least two frames: 0 <= start < end < 65 (inclusive)')
    sources = {}
    for d in DIRECTIONS:
        folder = batch / d;verify_result(folder)
        paths = sorted((folder / 'output').rglob('frame_*.png'))
        if [p.name for p in paths] != [f'frame_{i:06d}.png' for i in range(65)]:
            raise ValueError(f'Unexpected frame sequence: {d}')
        for p in paths[start:end+1]:
            with Image.open(p) as image:
                if image.size != (384, 384) or image.format != 'PNG':
                    raise ValueError(f'Unexpected selected frame: {d}')
        sources[d] = paths
    output.mkdir(exist_ok=False)
    receipt = {'batch': str(batch), 'start': start, 'endInclusive': end, 'directions': {},
               'scope': 'Exact RGB frame copies; no transparency, loop or visual-quality approval'}
    for d, paths in sources.items():
        dest = output / d;dest.mkdir();(dest / 'frames').mkdir();elapsed = 0;frames = []
        source_hashes = json.loads((batch / d / 'output-hashes.json').read_text())
        for i, p in enumerate(paths[start:end+1]):
            data = p.read_bytes();digest = hashlib.sha256(data).hexdigest()
            if digest != source_hashes[str(p.relative_to(batch / d / 'output'))]:
                raise ValueError(f'Source changed during copying: {d}/{p.name}')
            name = f'frames/{i+1:06d}.png';(dest / name).write_bytes(data)
            frames.append({'file': name, 'sha256': digest, 'sourceFrame': start+i, 'time': elapsed, 'duration': 1/24})
            elapsed += 1/24
        meta = {'version': 1, 'width': 384, 'height': 384, 'columns': 1, 'rows': 1,
                'frameCount': len(frames), 'durationSeconds': elapsed, 'reviewStatus': 'unreviewed',
                'source': {'batch': str(batch), 'direction': d, 'startFrame': start, 'endFrameInclusive': end,
                           'runSha256': hashlib.sha256((batch / d / 'run.json').read_bytes()).hexdigest()}, 'frames': frames}
        (dest / 'cycle.json').write_text(json.dumps(meta, indent=2)+'\n')
        receipt['directions'][d] = {'frames': len(frames), 'cycleSha256': hashlib.sha256((dest/'cycle.json').read_bytes()).hexdigest()}
    (output / 'extraction.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batch', type=Path, required=True);p.add_argument('--output', type=Path, required=True)
    p.add_argument('--start', type=int, required=True);p.add_argument('--end', type=int, required=True, help='Inclusive end frame')
    a=p.parse_args()
    try:extract(a.batch,a.output,a.start,a.end)
    except (OSError,ValueError,KeyError,TypeError) as exc:p.exit(2,f'Cycle extraction failed: {exc}\n')
    print(f'Extracted frames {a.start}..{a.end} in eight directions: {a.output}')

if __name__=='__main__':main()
