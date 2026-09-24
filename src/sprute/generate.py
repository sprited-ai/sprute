import json
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from sprute.comfy import run_workflow
from sprute.events import Event

WORKFLOW = Path("workflows/sprute-v2-generate-character.api.json")
TEMPLATE = Path("assets/sprute-v2-fill.png")

def generate(
    prompt: str,
    *,
    seed: int,
    out: Path,
    model_dirs: tuple[Path, ...] = (),
    on_event: Callable[[Event], None] | None = None,
) -> Path:
    def report(state, message, *, timed=False):
        if on_event is not None:
            on_event(Event(state, message, timed=timed))
    report("started", "Preparing generation", timed=True)
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["203"]["inputs"]["text"] = prompt
    graph["207"]["inputs"]["seed"] = seed
    template = TEMPLATE.resolve(strict=True)
    graph["17"]["inputs"]["image"] = template.name
    graph["114"]["inputs"]["filename_prefix"] = "reference"
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    model_dirs = tuple(
        directory.expanduser().resolve(strict=True)
        for directory in (model_dirs or (Path("models"),))
    )
    for directory in model_dirs:
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a model directory: {directory}")
    report("completed", "Generation prepared")
    report("started", "Generating character", timed=True)
    with TemporaryDirectory(prefix="sprute-generate-") as temporary:
        workflow_path = Path(temporary) / "workflow.json"
        workflow_path.write_text(json.dumps(graph), encoding="utf-8")
        # JSON is valid YAML, as expected by Comfy's extra model paths loader.
        paths_config = Path(temporary) / "model-paths.yaml"
        categories = ("checkpoints", "diffusion_models", "text_encoders", "clip_vision", "vae", "loras")
        paths_config.write_text(json.dumps({
            f"sprute_{index}": {
                "base_path": str(directory),
                **{category: category for category in categories},
            }
            for index, directory in enumerate(model_dirs)
        }), encoding="utf-8")
        # RMBG reads models_directory directly instead of extra model paths.
        rmbg_root = next(
            (directory for directory in model_dirs
             if (directory / "RMBG/BiRefNet/BiRefNet_toonout.safetensors").is_file()),
            model_dirs[0],
        )
        result = run_workflow(
            workflow_path,
            output=out,
            paths_config=paths_config,
            extra_args=(
                "--models-directory", str(rmbg_root),
                "--input-directory", str(template.parent),
            ),
            on_log=lambda message: report("log", message),
        )
    image = Path(result["114"]["images"][0]["abs_path"])
    if not image.is_file():
        raise RuntimeError(f"Generated image not found: {image}")
    report("completed", f"Character saved: {image}")
    return image
