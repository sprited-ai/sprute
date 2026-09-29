"""Replicate adapter; inference remains in Sprute's existing workflows."""
import json
import os
from pathlib import Path as LocalPath
import secrets
import shutil
import site
import sys
from tempfile import mkdtemp
from time import perf_counter

from cog import BasePredictor, Input, Path

ROOT = LocalPath(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from sprute.animate import animate
from sprute.config import set_models_directory
from sprute.generate import generate
from sprute.turntable import turntable
from deploy.replicate.metrics import PeakMemory


class Predictor(BasePredictor):
    def setup(self):
        os.chdir(ROOT)  # Committed workflows resolve assets relative to the checkout.
        set_models_directory(LocalPath(os.environ.get("SPRUTE_MODELS_DIRECTORY", ROOT / "models")))
        # Comfy runs in a child process. Prefer the CUDA libraries installed with
        # Torch over the older cuDNN shipped in the NVIDIA base image.
        libraries = [str(path) for directory in site.getsitepackages()
                     for path in LocalPath(directory).glob("nvidia/*/lib")]
        libraries.extend(filter(None, os.environ.get("LD_LIBRARY_PATH", "").split(":")))
        os.environ["LD_LIBRARY_PATH"] = ":".join(dict.fromkeys(libraries))
        self.output = None

    def predict(
        self,
        prompt: str = Input(default="", description="Describe a character. Used when no image is supplied."),
        image: Path | None = Input(default=None, description="Optional existing character or eight-direction strip; skips earlier stages."),
        image_type: str = Input(default="character", choices=["character", "directions"], description="What the uploaded image contains."),
        stop_after: str = Input(default="animate", choices=["generate", "turntable", "animate"], description="Last stage to run; all intermediate images are returned."),
        motions: str = Input(default="idle,walk,run", description="Comma-separated animations: idle, walk, run. Each runs independently."),
        seed: int = Input(default=-1, ge=-1, le=4294967295, description="-1 selects a random seed. The selected seed is shared by all stages."),
    ) -> list[Path]:
        stages = {"generate": 0, "turntable": 1, "animate": 2}
        if stop_after not in stages or image_type not in ("character", "directions"):
            raise ValueError("Invalid stage or image type")
        start = 0 if image is None else (1 if image_type == "character" else 2)
        end = stages[stop_after]
        if start > end:
            raise ValueError("stop_after is before the uploaded image's starting stage")
        if image is None and not prompt.strip():
            raise ValueError("Provide a prompt or an image")
        selected = list(dict.fromkeys(part.strip() for part in motions.split(",") if part.strip()))
        if end == 2 and (not selected or any(m not in ("idle", "walk", "run") for m in selected)):
            raise ValueError("motions must contain idle, walk and/or run")
        if not -1 <= seed <= 4294967295:
            raise ValueError("seed must be -1 or an unsigned 32-bit integer")
        if image is not None:
            image = LocalPath(image).resolve(strict=True)
        # Cog uploads a response before the next serial prediction begins.
        if self.output is not None:
            shutil.rmtree(self.output)
        self.output = LocalPath(mkdtemp(prefix="sprute-prediction-"))
        seed = secrets.randbits(32) if seed == -1 else seed
        records = []
        started = perf_counter()
        status = "failed"

        def run_stage(stage_name, function, *args, **kwargs):
            meter = PeakMemory()
            stage_status = "failed"
            try:
                with meter:
                    result = function(*args, seed=seed, out=self.output,
                                      on_event=lambda event: print(event.message, flush=True), **kwargs)
                stage_status = "succeeded"
                return result
            finally:
                record = dict(stage=stage_name, seed=seed, status=stage_status, **meter.result())
                records.append(record)
                print("SPRUTE_STAGE_METRICS " + json.dumps(record), flush=True)

        try:
            if image is not None:
                from PIL import Image
                # Normalize the upload and give downstream files predictable names.
                current = self.output / ("sprite.character.png" if start == 1 else "sprite.directions.png")
                with Image.open(image) as source:
                    source.convert("RGBA").save(current)
            else:
                current = run_stage("generate", generate, prompt, name="sprite")
            if start <= 1 <= end:
                current = run_stage("turntable", turntable, current)
            if end == 2:
                for motion in selected:
                    run_stage("animate:" + motion, animate, current, motion)
            status = "succeeded"
        finally:
            peaks = {}
            for record in records:
                for device, value in record["peak_device_memory_bytes"].items():
                    peaks[device] = max(peaks.get(device, 0), value)
            metrics = dict(seed=seed, status=status, stop_after=stop_after,
                           elapsed_seconds=round(perf_counter() - started, 3),
                           peak_device_memory_bytes=peaks,
                           peak_process_tree_rss_bytes=max((r["peak_process_tree_rss_bytes"] for r in records), default=None),
                           stages=records)
            (self.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
            print("SPRUTE_METRICS " + json.dumps(metrics), flush=True)
        return [Path(path) for path in sorted(self.output.iterdir()) if path.is_file()]
