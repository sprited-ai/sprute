"""Replicate adapter; inference remains in Sprute's existing workflows."""
import json
import os
from pathlib import Path as LocalPath
import secrets
import shutil
import sys
from tempfile import mkdtemp

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
        self.output = None

    def predict(
        self,
        operation: str = Input(default="generate", choices=["generate", "turntable", "animate"]),
        prompt: str = Input(default="", description="Character description for generate."),
        image: Path | None = Input(default=None, description="Character for turntable; eight-direction strip for animate."),
        motion: str = Input(default="idle", choices=["idle", "walk", "run"]),
        seed: int = Input(default=-1, ge=-1, le=4294967295, description="-1 selects a random seed."),
    ) -> list[Path]:
        if operation == "generate" and not prompt.strip():
            raise ValueError("generate requires a prompt")
        if operation in ("turntable", "animate") and image is None:
            raise ValueError(f"{operation} requires an image")
        if operation not in ("generate", "turntable", "animate"):
            raise ValueError(f"Unknown operation: {operation}")
        # Cog has uploaded the previous response before the next serial prediction.
        if self.output is not None:
            shutil.rmtree(self.output)
        self.output = LocalPath(mkdtemp(prefix="sprute-prediction-"))
        seed = secrets.randbits(32) if seed == -1 else seed
        meter = PeakMemory()
        try:
            with meter:
                kwargs = dict(seed=seed, out=self.output, on_event=lambda event: print(event.message, flush=True))
                if operation == "generate":
                    generate(prompt, **kwargs)
                elif operation == "turntable":
                    turntable(LocalPath(image), **kwargs)
                else:
                    animate(LocalPath(image), motion, **kwargs)
        finally:
            metrics = dict(operation=operation, seed=seed, **meter.result())
            (self.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
            print("SPRUTE_METRICS " + json.dumps(metrics), flush=True)
        return [Path(path) for path in sorted(self.output.iterdir()) if path.is_file()]
