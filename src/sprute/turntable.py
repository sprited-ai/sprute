import json
from pathlib import Path
from collections.abc import Callable
import secrets
from sprute.events import Event
from tempfile import TemporaryDirectory
from sprute.comfy import run_workflow

WORKFLOW = Path("workflows/sprute-v2-turntable-character.api.json")

def turntable(
    image: Path,
    *,
    seed: int | None = None,
    out: Path = Path("output"),
    model_dirs: tuple[Path, ...] = (),
    on_event: Callable[[Event], None] | None = None,
) -> Path:
    def report(state, message, *, timed=False):
        if on_event is not None:
            on_event(Event(state, message, timed=timed))
    image = image.expanduser().resolve(strict=True)
    if not image.is_file():
        raise ValueError(f"Not an image file: {image}")
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if seed is None:
        seed = secrets.randbits(32)
    name = image.stem.removesuffix(".character")
    destinations = {
        "17": out / f"{name}.turntable.webp",
        "28": out / f"{name}.directions.webp",
        "34": out / f"{name}.directions.png",
    }
    for destination in destinations.values():
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Output already exists: {destination}")
    model_dirs = tuple(
        directory.expanduser().resolve(strict=True)
        for directory in (model_dirs or (Path("models"),))
    )
    for directory in model_dirs:
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a model directory: {directory}")
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["1"]["inputs"]["image"] = image.name
    graph["18"]["inputs"]["seed"] = seed
    graph["17"]["inputs"]["filename_prefix"] = "turntable"
    graph["28"]["inputs"]["filename_prefix"] = "directions"
    graph["34"]["inputs"]["filename_prefix"] = "strip"
    report("started", f"Generating turntable · seed {seed}", timed=True)
    with TemporaryDirectory(prefix="sprute-turntable-") as temporary:
        directory = Path(temporary)
        workflow_path = directory / "workflow.json"
        workflow_path.write_text(json.dumps(graph), encoding="utf-8")

        result = run_workflow(
            workflow_path,
            output=directory / "output",
            model_dirs=model_dirs,
            extra_args=(
                "--input-directory", str(image.parent),
            ),
            on_log=lambda message: report("log", message),
        )

        sources = {}
        for node_id in destinations:
            saved = result[node_id]["images"][0]
            source = (
                Path(saved["abs_path"])
                if saved.get("abs_path")
                else directory / "output" / saved.get("subfolder", "") / saved["filename"]
            )
            if not source.is_file():
                raise FileNotFoundError(f"Turntable output not found: {source}")
            sources[node_id] = source

        created = []
        try:
            for node_id, destination in destinations.items():
                with destination.open("xb") as target:
                    created.append(destination)
                    target.write(sources[node_id].read_bytes())
        except BaseException:
            for destination in created:
                destination.unlink(missing_ok=True)
            raise

    strip = destinations["34"]
    report("completed", f"Turntable saved: {destinations['17']}")
    report("log", f"Direction preview saved: {destinations['28']}")
    report("completed", f"Directions saved: {strip}")
    return strip
