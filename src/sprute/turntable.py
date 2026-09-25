import json
from pathlib import Path
from collections.abc import Callable
import secrets
from sprute.events import Event
from sprute.comfy import run_workflow

WORKFLOW = Path("workflows/sprute-v2-turntable-character.api.json")

def turntable(
    image: Path,
    *,
    seed: int | None = None,
    out: Path = Path("output"),
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
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["1"]["inputs"]["image"] = image.name
    graph["18"]["inputs"]["seed"] = seed
    graph["17"]["inputs"]["filename_prefix"] = "turntable"
    graph["28"]["inputs"]["filename_prefix"] = "directions"
    graph["34"]["inputs"]["filename_prefix"] = "strip"
    report("started", f"Generating turntable · seed {seed}", timed=True)
    sources = run_workflow(
        graph,
        input_files=(image,),
        output_node_ids=tuple(destinations),
        on_log=lambda message: report("log", message),
    )
    created = []
    try:
        for node_id, destination in destinations.items():
            with destination.open("xb") as target:
                created.append(destination)
                target.write(sources[node_id])
    except BaseException:
        for destination in created:
            destination.unlink(missing_ok=True)
        raise

    strip = destinations["34"]
    report("completed", f"Turntable saved: {destinations['17']}")
    report("log", f"Direction preview saved: {destinations['28']}")
    report("completed", f"Directions saved: {strip}")
    return strip
