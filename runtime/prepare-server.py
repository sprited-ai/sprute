#!/usr/bin/env python3
"""Create an isolated pinned ComfyUI runtime on Linux x86_64 / Python 3.12."""
import argparse
import hashlib
import io
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import venv
import zipfile


def prepare(destination, lock, requirements):
    if sys.version_info[:2] != (3, 12) or platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('This runtime requires Linux x86_64 and Python 3.12. Run it on the GPU server.')
    if not shutil.which('git'):
        raise ValueError('Install git first.')
    destination = destination.absolute()
    destination.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'preparing', 'python': sys.version, 'platform': platform.platform(),
               'comfyCommit': lock['comfyUI']['commit'],
               'requirementsSha256': hashlib.sha256(requirements.read_bytes()).hexdigest()}
    def save():
        (destination/'setup.json').write_text(json.dumps(receipt, indent=2)+'\n')
    save()
    try:
        repo = destination/'ComfyUI'
        with (destination/'setup.log').open('w') as log:
            def run(args, cwd=None):
                print(' '.join(map(str, args)), flush=True)
                subprocess.run(list(map(str, args)), cwd=cwd, check=True, stdout=log, stderr=subprocess.STDOUT)
            run(['git', 'init', repo])
            run(['git', 'remote', 'add', 'origin', lock['comfyUI']['repository']], repo)
            run(['git', 'fetch', '--depth', '1', 'origin', lock['comfyUI']['commit']], repo)
            run(['git', 'checkout', '--detach', 'FETCH_HEAD'], repo)
            actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != lock['comfyUI']['commit']:
                raise ValueError('ComfyUI commit differs from the pin')
            node = lock['videoHelperSuite']
            print('Downloading pinned VideoHelperSuite', flush=True)
            with urllib.request.urlopen(node['downloadUrl'], timeout=60) as response:
                data = response.read(node['bytes']+1)
            if len(data) != node['bytes'] or hashlib.sha256(data).hexdigest() != node['sha256']:
                raise ValueError('VideoHelperSuite archive failed verification')
            (destination/'videohelpersuite.zip').write_bytes(data)
            folder = repo/'custom_nodes/comfyui-videohelpersuite'
            folder.mkdir()
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for member in archive.infolist():
                    target = folder/member.filename
                    if not target.resolve().is_relative_to(folder.resolve()) or member.file_size > 32*1024*1024:
                        raise ValueError('Invalid node archive member')
                    if member.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with target.open('xb') as output:
                            output.write(archive.read(member))
            # Keep this path fixed: moving a venv would invalidate its shebangs.
            print('Creating Python environment', flush=True)
            venv.create(destination/'venv', with_pip=True)
            python = destination/'venv/bin/python'
            copied = destination/'requirements-hashed.txt'
            shutil.copyfile(requirements, copied)
            run([python, '-m', 'pip', '--isolated', 'install', '--require-hashes', '--no-index', '--only-binary=:all:', '--report', destination/'install-report.json', '-r', copied])
            run([python, '-m', 'pip', 'check'])
            with (destination/'freeze.txt').open('w') as output:
                subprocess.run([str(python), '-m', 'pip', 'freeze'], stdout=output, check=True)
        receipt['status'] = 'installed'
        receipt['scope'] = 'Code and Python dependencies installed; models, GPU execution and motion guides are separate.'
        save()
        print('Server runtime installed at', destination)
        print('Next: install model files into', repo/'models')
        print('Start from the ComfyUI directory using ../venv/bin/python main.py --listen 127.0.0.1 --port 8188')
    except BaseException as error:
        receipt.update(status='failed', error=str(error))
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('new_directory', type=Path, help='A new directory for code, dependencies and installation logs')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        prepare(args.new_directory, json.loads((root/'docs/animation-runtime-lock.json').read_text()), root/'runtime/requirements-linux-cu128-hashed.txt')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
