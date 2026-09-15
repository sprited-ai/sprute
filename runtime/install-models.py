#!/usr/bin/env python3
"""Install pinned walking model files, verifying bytes before publishing them."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlparse
from urllib.request import urlopen

spec = importlib.util.spec_from_file_location('verify_models', Path(__file__).with_name('verify-models.py'))
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def validate(manifest):
    models = manifest['models']
    if not models:
        raise ValueError('The manifest has no models')
    paths = set()
    for model in models:
        path = Path(model['relativePath'])
        if path.is_absolute() or '..' in path.parts or str(path) == '.' or str(path) in paths:
            raise ValueError('Model paths must be unique relative file paths without ..')
        paths.add(str(path))
        if type(model['bytes']) is not int or model['bytes'] <= 0:
            raise ValueError('Expected a positive model byte count')
        if not re.fullmatch('[0-9a-f]{64}', model['publishedSha256']):
            raise ValueError('Expected a lowercase SHA256 digest')
        url = urlparse(model['downloadUrl'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('Download URLs must use HTTPS without embedded credentials')
    return models


def install(root, manifest, opener=urlopen):
    models = validate(manifest)
    results = []
    for model in models:
        destination = root / model['relativePath']
        print('Checking ' + model['relativePath'], file=sys.stderr, flush=True)
        if os.path.lexists(destination):
            result = verifier.verify(root, {'models': [model]})
            if not result['ok']:
                raise ValueError('Existing model differs or is unreadable; left unchanged: ' + str(destination))
            results.append({'path': model['relativePath'], 'action': 'reused'})
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Same-filesystem temporary file + exclusive hard-link publication avoids
        # exposing partial weights and never replaces a concurrent installation.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.' + destination.name + '.', suffix='.partial', delete=False) as target:
                temporary = Path(target.name)
                digest = hashlib.sha256()
                count = 0
                last_progress = time.monotonic()
                print('Downloading ' + model['relativePath'], file=sys.stderr, flush=True)
                with opener(model['downloadUrl'], timeout=60) as response:
                    if urlparse(response.geturl()).scheme != 'https':
                        raise ValueError('Refusing a non-HTTPS download redirect')
                    while True:
                        chunk = response.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > model['bytes']:
                            raise ValueError('Download exceeds expected size: ' + model['relativePath'])
                        digest.update(chunk)
                        target.write(chunk)
                        now = time.monotonic()
                        if now - last_progress >= 10:
                            print(f"{model['relativePath']}: {count / 2**20:.1f} / {model['bytes'] / 2**20:.1f} MiB ({count / model['bytes']:.0%})", file=sys.stderr, flush=True)
                            last_progress = now
                if count != model['bytes'] or digest.hexdigest() != model['publishedSha256']:
                    raise ValueError('Downloaded model failed size/SHA256 verification: ' + model['relativePath'])
                target.flush()
                os.fsync(target.fileno())
            os.link(temporary, destination)
            print('Verified ' + model['relativePath'], file=sys.stderr, flush=True)
            results.append({'path': model['relativePath'], 'action': 'installed', 'bytes': count, 'sha256': digest.hexdigest()})
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {'ok': True, 'models': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('models_directory', type=Path, help='Model root matching the selected manifest (for example ComfyUI/models)')
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/animation-scail-models.json')
    args = parser.parse_args()
    try:
        result = install(args.models_directory, json.loads(args.manifest.read_text()))
    except (OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
