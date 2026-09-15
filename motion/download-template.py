#!/usr/bin/env python3
"""Download and verify the CC0 Quaternius GLB supported by Sprute's renderer."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import tempfile
import sys
import urllib.request
import zipfile

URL = 'https://opengameart.org/sites/default/files/universal_animation_librarystandard.zip'
ARCHIVE_BYTES = 14541205
ARCHIVE_SHA256 = '18ff1a7215f4852b320203e8aaf02a1578b5c8eef9027fbaedfcedc7b85a3ac2'
MEMBER = 'Animation Library[Standard]/Godot/AnimationLibrary_Godot_Standard.glb'
MODEL_BYTES = 6671104
MODEL_SHA256 = '1b7bf67866360665426bb99e4c71bd619f19b408453c24e30f0c3071601eee5c'


def download(output):
    if os.path.lexists(output):
        raise FileExistsError('Output already exists: ' + str(output))
    print('Downloading the supported Quaternius template (14.5 MB)…', flush=True)
    with urllib.request.urlopen(URL, timeout=60) as response:
        archive = response.read(ARCHIVE_BYTES + 1)
    if len(archive) != ARCHIVE_BYTES or hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Archive differs from the supported version. No model was saved.')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        info = z.getinfo(MEMBER)
        if info.file_size != MODEL_BYTES:
            raise ValueError('Unexpected model size in archive')
        data = z.read(info)
    if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
        raise ValueError('Model hash differs from the supported version')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.sprute-template-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print('Verified template saved:', output)
    print('Creator: Quaternius · CC0 1.0 · See motion/QUATERNIUS-LICENSE.txt')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('new_glb_file', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None)
    try:
        download(args.new_glb_file.absolute())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error)+'\n')


if __name__ == '__main__':
    main()
