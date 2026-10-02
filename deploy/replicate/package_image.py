"""Repackage a validated Cog build with separate bundled weight layers.

The registry rejected the original all-models layer. Reuse the generated runtime
instructions, copy each weight separately, and retain Cog's metadata verbatim.
"""
import argparse
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


BASE = "python:3.12.14-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f"


def package_image(source_image: str, tag: str, cog: str) -> None:
    from deploy.replicate.check_image import check_image

    check_image(source_image, base_image=BASE)
    metadata = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", source_image], text=True,
    ))[0]
    generated = subprocess.check_output(
        [cog, "debug", "--use-cuda-base-image=false"], text=True,
    )
    if generated.count("COPY . /src") != 1:
        raise RuntimeError("Cog Dockerfile format changed; inspect before packaging")
    generated = generated.replace("FROM python:3.12.14-slim\n", f"FROM {BASE}\n", 1)
    if f"FROM {BASE}\n" not in generated:
        raise RuntimeError("Unexpected generated base image")

    copies = []
    for name in ("assets", "src", "custom_nodes", "workflows", "motions", "deploy",
                 "predict.py", "pyproject.toml", "cog.yaml", "README.md", "LICENSE"):
        if not Path(name).exists():
            raise FileNotFoundError(name)
        copies.append("COPY " + json.dumps([name, f"/src/{name}"]))

    manifest = Path("models/.parts/manifest.json")
    if not manifest.is_file():
        raise RuntimeError("Prepare split FLUX weights before packaging")
    split_targets = {Path("models") / entry["destination"]
                     for entry in json.loads(manifest.read_text())}
    excluded = Path("models/diffusion_models/wan2.1_14B_SCAIL_2_fp16.safetensors")
    for path in sorted(Path("models").rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Bundled weights must be real files: {path}")
        if not path.is_file() or path in split_targets or path == excluded:
            continue
        copies.append("COPY " + json.dumps([str(path), f"/src/{path}"]))
    generated = generated.replace("COPY . /src", "\n".join(copies))

    with TemporaryDirectory(prefix="sprute-package-") as directory:
        directory = Path(directory)
        container = subprocess.check_output(
            ["docker", "create", metadata["Id"]], text=True,
        ).strip()
        try:
            subprocess.run(["docker", "cp", f"{container}:/tmp/requirements.txt",
                            str(directory / "requirements.txt")], check=True)
        finally:
            subprocess.run(["docker", "rm", container], check=True)
        dockerfile = directory / "Dockerfile"
        dockerfile.write_text(generated)
        command = ["docker", "build", "--build-context", f"cog_build={directory}",
                   "-f", str(dockerfile), "-t", tag]
        # Pass labels as arguments; Dockerfile interpolation would corrupt $ref.
        for key, value in metadata["Config"]["Labels"].items():
            command.extend(["--label", f"{key}={value}"])
        subprocess.run([*command, "."], check=True)
    check_image(tag, base_image=BASE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_image")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--cog", default="cog")
    args = parser.parse_args()
    package_image(args.source_image, args.tag, args.cog)
