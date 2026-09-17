"""Small file/provenance helpers. No credentials are persisted."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    tmp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def file_record(path):
    p = Path(path).resolve(strict=True)
    return {'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size}


def pin(path, value):
    """A run folder belongs to exactly one set of inputs/settings."""
    path = Path(path)
    if path.exists() and read(path) != value:
        raise RuntimeError(f'Inputs/settings changed: {path}. Use a new output directory.')
    write(path, value)


@contextlib.contextmanager
def lock(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / '.lock').open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'Another process owns {folder}') from None
        yield


def json_request(url, data=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={'Content-Type': 'application/json', **(headers or {})})
    with urllib.request.urlopen(req, timeout=90) as res:
        return json.load(res)


def download(url, path):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.download')
    with urllib.request.urlopen(url, timeout=180) as response, tmp.open('wb') as f:
        import shutil
        shutil.copyfileobj(response, f)
    tmp.replace(path)


def token():
    value = os.environ.get('REPLICATE_API_TOKEN')
    if not value:
        raise RuntimeError('Set REPLICATE_API_TOKEN in the environment. No login is needed.')
    return value


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
