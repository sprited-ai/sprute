#!/usr/bin/env python3
"""Read-only full-file verification of a Sprute server model manifest."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(root, manifest):
    results = []
    for model in manifest['models']:
        relative = Path(model['relativePath'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Model paths must be relative and must not contain ..')
        entry = {'path': str(relative), 'expectedBytes': model['bytes'],
                 'expectedSha256': model['publishedSha256']}
        try:
            # Symlinks are supported: existing installations often share weights.
            with (root / relative).open('rb') as stream:
                import os
                before = os.fstat(stream.fileno())
                digest = hashlib.sha256()
                count = 0
                for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                    digest.update(chunk)
                    count += len(chunk)
                after = os.fstat(stream.fileno())
            current = (root / relative).stat()
            signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            stable = signature(before) == signature(after) == signature(current)
            entry.update(bytes=count, sha256=digest.hexdigest(), stableDuringRead=stable)
            entry['ok'] = stable and count == model['bytes'] and digest.hexdigest() == model['publishedSha256']
        except OSError as error:
            entry.update(ok=False, error=str(error))
        results.append(entry)
    return {'ok': bool(results) and all(x['ok'] for x in results), 'models': results,
            'scope': 'File identity only; no inference, VRAM or visual-quality check.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('models_directory', type=Path, help='Model root matching the selected manifest (for example ComfyUI/models)')
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/animation-scail-models.json')
    args = parser.parse_args()
    result = verify(args.models_directory, json.loads(args.manifest.read_text()))
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
