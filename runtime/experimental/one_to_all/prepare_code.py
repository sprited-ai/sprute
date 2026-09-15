"""Prepare a pinned One-to-All checkout without changing neural implementations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import os


def prepare(checkout, *, check=False):
    root = Path(checkout).resolve()
    manifest = json.loads(Path(__file__).with_name('code-patches.json').read_text())
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != manifest['commit']:
        raise ValueError('Unsupported checkout commit')
    pending, results = [], []
    # Validate all targets before changing any target. Already prepared files are
    # accepted to allow recovery after an interruption between writes.
    for item in manifest['files']:
        target = root / item['path']
        if not target.resolve().is_relative_to(root) or target.is_symlink():
            raise ValueError('Patch target escapes checkout or is a symlink')
        current = target.read_bytes()
        replacement = item['replacement'].encode()
        digest = hashlib.sha256(current).hexdigest()
        if current == replacement:
            status = 'prepared'
        elif digest == item['originalSha256']:
            status = 'original'
            pending.append((target, replacement))
        else:
            raise ValueError('Unexpected file content: ' + item['path'])
        results.append({'path': item['path'], 'status': status,
                        'preparedSha256': hashlib.sha256(replacement).hexdigest()})
    if not check:
        for target, replacement in pending:
            fd, name = tempfile.mkstemp(prefix='.sprute-patch-', dir=target.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(replacement)
                os.chmod(name, target.stat().st_mode & 0o777)
                os.replace(name, target)
            finally:
                Path(name).unlink(missing_ok=True)
    return {'commit': commit, 'checkOnly': check, 'files': results,
            'changedFiles': 0 if check else len(pending)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    parser.add_argument('--check', action='store_true', help='Validate without writing')
    args = parser.parse_args()
    print(json.dumps(prepare(args.checkout, check=args.check), indent=2))


if __name__ == '__main__':
    main()
