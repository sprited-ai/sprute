"""Check release metadata and Python bootstrap without network or GPU use.

Run before pushing: python -m deploy.replicate.check_image IMAGE
This does not replace a Cog server readiness check or hosted inference test.
"""
import argparse
import json
import subprocess

from deploy.replicate.smoke import validate_schema


def check_image(image: str, *, base_image: str | None = None) -> None:
    metadata = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", image], text=True, timeout=30,
    ))[0]
    schema = metadata["Config"]["Labels"]["run.cog.openapi_schema"]
    validate_schema(json.loads(schema))
    if base_image is not None:
        base = json.loads(subprocess.check_output(
            ["docker", "image", "inspect", base_image], text=True, timeout=30,
        ))[0]
        layers = base["RootFS"]["Layers"]
        if metadata["RootFS"]["Layers"][:len(layers)] != layers:
            raise RuntimeError(f"Image does not use the expected base: {base_image}")
        print(f"Base image layers match {base_image}", flush=True)
    # Pin the inspected image ID so a concurrent tag update cannot change it.
    probe = """
import importlib.metadata as metadata
from pathlib import Path
import subprocess
import sys
import sysconfig
import platform
import torch
import requests_cache  # Detect cattrs/attrs incompatibility before Comfy starts.
marker = Path(sysconfig.get_path('stdlib')) / 'EXTERNALLY-MANAGED'
if marker.exists():
    raise RuntimeError('Replicate bootstrap is blocked by EXTERNALLY-MANAGED')
cog = metadata.version('cog')
print(f'Python: {sys.executable}; Cog: {cog}', flush=True)
expected = {'python': '3.12.14', 'torch': '2.11.0+cu128',
            'torchvision': '0.26.0+cu128', 'cuda': '12.8', 'cog': '0.16.8'}
actual = {'python': platform.python_version(), 'torch': torch.__version__,
          'torchvision': metadata.version('torchvision'),
          'cuda': torch.version.cuda, 'cog': cog}
if actual != expected:
    raise RuntimeError(f'Runtime differs from validated SCAIL-2 stack: {actual}')
print(f'Runtime versions match: {actual}', flush=True)
subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True, timeout=30)
subprocess.run([sys.executable, '-m', 'pip', 'install', '--dry-run',
                '--no-index', f'cog=={cog}'], check=True, timeout=30)
"""
    subprocess.run([
        "docker", "run", "--rm", "--network", "none", "--entrypoint", "python",
        metadata["Id"], "-c", probe,
    ], check=True, timeout=60)
    print("Image schema and Python bootstrap checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--base-image", help="Local base image whose filesystem layers must match")
    args = parser.parse_args()
    check_image(args.image, base_image=args.base_image)
