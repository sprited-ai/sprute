import json
from PIL import Image
import math
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from sprute.comfy import input_name, run_workflow, same_workflow, saved_workflow
from sprute.events import Event
from sprute.motion import find_motion

WORKFLOW = Path("workflows/sprute-animate-character.api.json")
MOTIONS = ("idle", "walk", "run")

def animate(
    directions: Path,
    motion: str,
    *,
    seed: int | None = None,
    draft: bool = False,
    scale: float = 1.0,
    every: int = 2,
    snap: bool = True,
    out: Path = Path("output"),
    on_event: Callable[[Event], None] | None = None,
) -> Path:
    if isinstance(every, bool) or not isinstance(every, int) or every < 1:
        raise ValueError("every must be a positive integer")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("scale must be a finite number greater than zero")
    if draft:
        if scale not in (1.0, 0.5):
            raise ValueError("--draft is equivalent to --scale 0.5; choose one")
        scale = 0.5

    def report(state, message, *, timed=False):
        if on_event is not None:
            on_event(Event(state, message, timed=timed))
    motion_file = find_motion(motion).resolve()
    directions = directions.expanduser().resolve(strict=True)
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if seed is None:
        seed = secrets.randbits(32)
    name = directions.stem.removesuffix(".directions")
    motion_name = motion_file.stem
    destination = out / f"{name}.{motion_name}.webp"
    directions_name = input_name(directions)
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["3"]["inputs"]["image"] = directions_name
    with Image.open(directions) as reference:
        width = reference.width
    if width % 8:
        raise ValueError("Directions image must contain eight equal-width cells")
    # The workflow renders the GLB into the driving video itself, in cells measured from the directions image.
    motion_input = input_name(motion_file)
    graph["601"]["inputs"]["motion"] = motion_input
    # The motion's length snaps to a multiple of every frames, so the frames kept land on its ends.
    if not snap:
        graph["4"]["inputs"]["snap_to_multiple"] = 0
    graph["504"]["inputs"]["seed"] = seed
    # Scale inference inputs together; the workflow restores the output size.
    graph["587"]["inputs"]["value"] = scale
    graph["577"]["inputs"]["filename_prefix"] = motion_name
    graph["598"]["inputs"]["value"] = every
    if destination.is_file() and same_workflow(saved_workflow(destination), graph):
        report("completed", f"Animation unchanged: {destination}")
        return destination
    report("started", f"Animating {motion} from {motion_file.name} · seed {seed}{f' · scale {scale:g}' if scale != 1.0 else ''}", timed=True)
    data = run_workflow(
        graph,
        input_files={directions_name: directions, motion_input: motion_file},
        output_node_ids=("577",),
        on_event=on_event,
    )["577"]
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    report("completed", f"Animation saved: {destination}")
    return destination
