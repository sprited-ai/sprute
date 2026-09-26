import json
import os
from pathlib import Path
from collections.abc import Callable
import secrets
from sprute.events import Event
from sprute.comfy import input_name, run_workflow
from PIL import Image

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
    image_name = input_name(image)
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["1"]["inputs"]["image"] = image_name
    graph["18"]["inputs"]["seed"] = seed
    graph["17"]["inputs"]["filename_prefix"] = "turntable"
    graph["28"]["inputs"]["filename_prefix"] = "directions"
    graph["34"]["inputs"]["filename_prefix"] = "strip"
    strip = destinations["34"]
    if all(destination.is_file() for destination in destinations.values()) and same_workflow(saved_workflow(strip), graph):
        report("completed", f"Turntable unchanged: {destinations['17']}")
        report("completed", f"Directions unchanged: {strip}")
        return strip
    report("started", f"Generating turntable · seed {seed}", timed=True)
    sources = run_workflow(
        graph,
        input_files={image_name: image},
        output_node_ids=tuple(destinations),
        on_log=lambda message: report("log", message),
    )
    # Write every output before replacing any, so a failure leaves the old set intact.
    temporaries = {node_id: destination.with_name(f".{destination.name}.tmp") for node_id, destination in destinations.items()}
    try:
        for node_id, temporary in temporaries.items():
            temporary.write_bytes(sources[node_id])
        for node_id, temporary in temporaries.items():
            os.replace(temporary, destinations[node_id])
    finally:
        for temporary in temporaries.values():
            temporary.unlink(missing_ok=True)

    report("completed", f"Turntable saved: {destinations['17']}")
    report("log", f"Direction preview saved: {destinations['28']}")
    report("completed", f"Directions saved: {strip}")
    return strip


def saved_workflow(path: Path) -> dict | None:
    """Read the API workflow ComfyUI embeds in a saved PNG."""
    try:
        with Image.open(path) as image:
            return json.loads(image.info["prompt"])
    except (OSError, KeyError, ValueError):
        return None


def same_workflow(saved: dict | None, workflow: dict) -> bool:
    """Compare what runs; ComfyUI adds bookkeeping such as is_changed when saving."""
    def runnable(nodes: dict) -> dict:
        return {node_id: (node.get("class_type"), node.get("inputs")) for node_id, node in nodes.items()}
    return saved is not None and runnable(saved) == runnable(workflow)
