"""Check release metadata and Python bootstrap without network or GPU use.

Run before pushing: python -m deploy.replicate.check_image IMAGE
This does not replace a Cog server readiness check or hosted inference test.
"""
import argparse
import json
import subprocess

from deploy.replicate.smoke import validate_schema


def check_image(image: str) -> None:
    metadata = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", image], text=True, timeout=30,
    ))[0]
    schema = metadata["Config"]["Labels"]["run.cog.openapi_schema"]
    validate_schema(json.loads(schema))
    # Pin the inspected image ID so a concurrent tag update cannot change it.
    probe = """
import importlib.metadata as metadata
from pathlib import Path
import subprocess
import sys
import sysconfig
marker = Path(sysconfig.get_path('stdlib')) / 'EXTERNALLY-MANAGED'
if marker.exists():
    raise RuntimeError('Replicate bootstrap is blocked by EXTERNALLY-MANAGED')
cog = metadata.version('cog')
print(f'Python: {sys.executable}; Cog: {cog}', flush=True)
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
    check_image(parser.parse_args().image)
