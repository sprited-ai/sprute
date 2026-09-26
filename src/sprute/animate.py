import json
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from sprute.comfy import input_name, run_workflow, same_workflow, saved_workflow
from sprute.events import Event

WORKFLOW = Path("workflows/sprute-animate-character.api.json")
PRESETS = ("idle", "walk", "run")

def animate(
    directions: Path,
    preset: str,
    *,
    seed: int | None = None,
    out: Path = Path("output"),
    on_event: Callable[[Event], None] | None = None,
) -> Path:
    def report(state, message, *, timed=False):
        if on_event is not None:
            on_event(Event(state, message, timed=timed))
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset {preset!r}; choose one of: {', '.join(PRESETS)}")
    directions = directions.expanduser().resolve(strict=True)
    motion = Path(f"assets/sprute-{preset}-81.576.webp").resolve(strict=True)
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if seed is None:
        seed = secrets.randbits(32)
    name = directions.stem.removesuffix(".directions")
    destination = out / f"{name}.{preset}.webp"
    directions_name = input_name(directions)
    motion_name = input_name(motion)
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["3"]["inputs"]["image"] = directions_name
    graph["4"]["inputs"]["image"] = motion_name
    graph["504"]["inputs"]["seed"] = seed
    graph["577"]["inputs"]["filename_prefix"] = preset
    if destination.is_file() and same_workflow(saved_workflow(destination), graph):
        report("completed", f"Animation unchanged: {destination}")
        return destination
    report("started", f"Animating {preset} · seed {seed}", timed=True)
    data = run_workflow(
        graph,
        input_files={directions_name: directions, motion_name: motion},
        output_node_ids=("577",),
        on_log=lambda message: report("log", message),
    )["577"]
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    report("completed", f"Animation saved: {destination}")
    return destination
