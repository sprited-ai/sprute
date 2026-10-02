"""Download pinned weights once per worker, outside Cog's setup deadline."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
from time import monotonic

# Replicate's injected HF proxy currently returns truncated response bodies.
# Use the public origin for these public, revision-pinned model files.
# Set before importing huggingface_hub, which reads these at import time.
os.environ["HF_ENDPOINT"] = "https://huggingface.co"
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ.pop("HF_HUB_ENABLE_HF_TRANSFER", None)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from sprute.models import check_download_space, download_model
from huggingface_hub.utils import disable_progress_bars

MANIFEST = Path(__file__).with_name("weights-manifest.json")
BACKGROUND = ("toonout", "birefnet-code", "birefnet-config-code", "birefnet-config")
STAGES = {
    "generate": ("flux-fill", "clip-l", "t5-xxl", "flux-vae", *BACKGROUND),
    "turntable": ("anisora-high", "anisora-low", "umt5-xxl", "clip-vision-h", "wan-vae", *BACKGROUND),
    "animate": ("scail2", "scail2-dpo", "lightx2v", "umt5-xxl", "clip-vision-h", "wan-vae-bf16", *BACKGROUND),
}


def required_models(inputs):
    stages = list(STAGES)
    end = stages.index(inputs["stop_after"])
    start = 0 if not inputs.get("image") else (1 if inputs["image_type"] == "character" else 2)
    if start > end:
        raise ValueError("stop_after is before the uploaded image's starting stage")
    if start == 0 and not inputs.get("prompt", "").strip():
        raise ValueError("Provide a prompt or an image")
    return list(dict.fromkeys(name for stage in stages[start:end + 1] for name in STAGES[stage]))


def fingerprint(path, sha256):
    stat = path.stat()
    return dict(sha256=sha256, size=stat.st_size, mtime_ns=stat.st_mtime_ns)


def ensure_weights(inputs, directory, *, manifest=None):
    disable_progress_bars()
    manifest = manifest if manifest is not None else json.loads(MANIFEST.read_text())
    names = required_models(inputs)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # Cog is sequential today; also protect a cache shared by local test workers.
    with (directory / ".download.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        missing = []
        for name in names:
            entry = manifest[name]
            target = directory / entry["destination"]
            marker = target.with_name(target.name + ".verified.json")
            valid = False
            if target.is_file() and target.stat().st_size == entry["size"]:
                try:
                    valid = json.loads(marker.read_text()) == fingerprint(target, entry["sha256"])
                except (OSError, ValueError):
                    pass
                if not valid:
                    with target.open("rb") as stream:
                        valid = hashlib.file_digest(stream, "sha256").hexdigest() == entry["sha256"]
                    if valid:
                        marker.write_text(json.dumps(fingerprint(target, entry["sha256"])))
            if not valid:
                missing.append(name)
        required = sum(manifest[name]["size"] for name in missing)
        print(f"[weights] {len(names) - len(missing)}/{len(names)} cached; {required / 1e9:.2f} GB to download", flush=True)
        check_download_space(required, directory)

        def fetch(name):
            entry = manifest[name]
            target = directory / entry["destination"]
            # This directory belongs to the hosted worker, never a user's model folder.
            target.unlink(missing_ok=True)
            started = monotonic()
            print(f"[weights] Downloading {name} ({entry['size'] / 1e9:.2f} GB)", flush=True)
            download_model(entry["repo_id"], entry["filename"], revision=entry["revision"],
                           destination=target)
            with target.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if target.stat().st_size != entry["size"] or digest != entry["sha256"]:
                target.unlink()
                raise RuntimeError(f"Downloaded weight integrity check failed: {name}")
            target.with_name(target.name + ".verified.json").write_text(json.dumps(fingerprint(target, digest)))
            print(f"[weights] Verified {name} in {monotonic() - started:.1f}s", flush=True)

        started = monotonic()
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(fetch, missing))
        print(f"[weights] Ready in {monotonic() - started:.1f}s", flush=True)


if __name__ == "__main__":
    ensure_weights(json.loads(Path(sys.argv[1]).read_text()),
                   os.environ.get("SPRUTE_MODELS_DIRECTORY", "/src/models"))
