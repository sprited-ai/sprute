"""Reuse the validated runtime, excluding every bundled model layer.

Run on gin: python -m deploy.replicate.package_lazy_image SOURCE --tag TAG
SOURCE must pass check_image and use the pinned SCAIL-compatible Python base.
"""
import argparse
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from deploy.replicate.check_image import check_image
from deploy.replicate.package_image import BASE


def package(source, tag):
    check_image(source, base_image=BASE)
    metadata = json.loads(subprocess.check_output(["docker", "image", "inspect", source]))[0]
    config = metadata["Config"]
    lines = [f"FROM {source} AS source", f"FROM {BASE}"]
    # Copy the runtime filesystem into a fresh base. Deleting weights from a
    # full-image descendant would leave all weight bytes in its parent layers.
    for name in ("usr", "etc", "var", "opt", "root", "tmp", "home", "run", "srv", "mnt", "media"):
        lines.append("COPY --from=source " + json.dumps([f"/{name}/", f"/{name}/"]))
    for name in ("assets", "src", "custom_nodes", "workflows", "motions", "deploy",
                 "predict.py", "pyproject.toml", "cog.yaml", "README.md", "LICENSE"):
        lines.append("COPY " + json.dumps([name, f"/src/{name}"]))
    for env in config["Env"]:
        key, value = env.split("=", 1)
        lines.append(f"ENV {key}=" + json.dumps(value))
    lines.extend(["ENV SPRUTE_LAZY_WEIGHTS=1", "WORKDIR /src", "EXPOSE 5000",
                  "ENTRYPOINT " + json.dumps(config["Entrypoint"]),
                  "CMD " + json.dumps(config["Cmd"])])
    with TemporaryDirectory() as temporary:
        dockerfile = Path(temporary) / "Dockerfile"
        dockerfile.write_text("\n".join(lines) + "\n")
        command = ["docker", "build", "-f", str(dockerfile), "-t", tag]
        for key, value in config["Labels"].items():
            command.extend(["--label", f"{key}={value}"])
        subprocess.run([*command, "."], check=True)
    check_image(tag, base_image=BASE)
    subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python", tag,
                    "-c", "from pathlib import Path; assert not Path('/src/models').exists()"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    package(args.source, args.tag)
