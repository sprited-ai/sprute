"""Prepare eight standing references and detected skeletons for motion fitting.

Detection is not anatomy approval. In particular, rear-facing facial landmarks
may be hallucinated; downstream rendering still requires a head policy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

DIRECTIONS = ['S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW']


def prepare_references(sheet, runtime, output):
    import numpy as np
    from PIL import Image, ImageDraw
    sheet, runtime, output = map(lambda p: Path(p).resolve(), (sheet, runtime, output))
    source_bytes = sheet.read_bytes()
    with Image.open(sheet) as source:
        source.load()
        if source.width != 8 * source.height:
            raise ValueError('Expected one horizontal row of eight square standing cells')
        if 'A' not in source.getbands():
            raise ValueError('Standing sheet must contain an alpha channel')
        source = source.convert('RGBA')
    references = []
    for index, direction in enumerate(DIRECTIONS):
        size = source.height
        cell = source.crop((index * size, 0, (index + 1) * size, size))
        bbox = cell.getchannel('A').point(lambda a: 255 if a >= 16 else 0).getbbox()
        if bbox is None:
            raise ValueError(f'Empty reference: {direction}')
        crop = cell.crop(bbox)
        scale = min(360 / crop.height, 400 / crop.width)
        resized = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.Resampling.NEAREST)
        canvas = Image.new('RGBA', (512, 512), (220, 220, 220, 255))
        canvas.alpha_composite(resized, ((512 - resized.width) // 2, 420 - resized.height))
        references.append((direction, canvas.convert('RGB'), bbox, scale))
    sys.path.insert(0, str(runtime / 'code'))
    from wanpose_utils.pose2d import Pose2d
    model = Pose2d(str(runtime / 'models/process_checkpoint/pose2d/vitpose_h_wholebody.onnx'),
                   detector_checkpoint=str(runtime / 'models/process_checkpoint/det/yolov10m.onnx'), device='cpu')
    output.mkdir(parents=False, exist_ok=False)
    receipt = {'status': 'running', 'sourceSha256': hashlib.sha256(source_bytes).hexdigest(),
               'source': str(sheet), 'poseRuntime': str(runtime), 'directions': {},
               'reviewStatus': 'unreviewed', 'scope': 'Detected landmarks, not approved anatomy or visibility'}
    def save():
        temp = output / 'references.json.tmp'
        temp.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
        temp.replace(output / 'references.json')
    try:
        save()
        for direction, image, bbox, scale in references:
            start = time.monotonic()
            folder = output / direction
            folder.mkdir()
            image.save(folder / 'reference.png')
            meta = model([np.array(image)])[0]
            meta = {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in meta.items()}
            for name, count in [('body', 20), ('face', 69), ('left_hand', 21), ('right_hand', 21)]:
                points = np.asarray(meta[f'keypoints_{name}'])
                if points.shape != (count, 3) or not np.isfinite(points).all():
                    raise ValueError(f'Invalid {name} landmarks in {direction}')
            (folder / 'reference.json').write_text(json.dumps(meta, indent=2, allow_nan=False) + '\n')
            overlay = image.copy()
            draw = ImageDraw.Draw(overlay)
            for i, (x, y, confidence) in enumerate(meta['keypoints_body']):
                if confidence < .3:
                    continue
                x, y = x * 512, y * 512
                draw.ellipse((x-3, y-3, x+3, y+3), fill='cyan')
                draw.text((x+4, y-8), str(i), fill='cyan', stroke_width=1, stroke_fill='black')
            overlay.save(folder / 'overlay.png')
            receipt['directions'][direction] = {
                'sourceBBox': bbox, 'scale': scale,
                'coreAbove03': sum(p[2] >= .3 for p in meta['keypoints_body'][1:14]),
                'seconds': time.monotonic() - start,
                'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()},
            }
            save()
            print(f'Prepared {direction} ({len(receipt["directions"])}/8)', flush=True)
        receipt['status'] = 'complete'
        save()
    except BaseException as error:
        receipt.update(status='failed', error=str(error))
        save()
        raise
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sheet', required=True, type=Path)
    parser.add_argument('--pose-runtime', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    prepare_references(args.sheet, args.pose_runtime, args.output)
