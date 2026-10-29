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
# Seedance 2.0 on Replicate, with the user's token, by --use name; SCAIL2 runs locally.
SEEDANCE = {"seedance": "seedance-2.0-fast", "seedance-pro": "seedance-2.0"}
BACKENDS = ("scail2", *SEEDANCE)
SEEDANCE_SECONDS = 4
# US dollars per second of Seedance output with a video input, as Replicate bills it.
SEEDANCE_PRICE = {"seedance-2.0-fast": 0.08, "seedance-2.0": 0.10}


def cost(backend: str) -> float:
    """What one animation costs on Replicate; nothing for SCAIL2, which runs locally."""
    return SEEDANCE_PRICE[SEEDANCE[backend]] * SEEDANCE_SECONDS if backend in SEEDANCE else 0.0


def reachable(graph: dict, outputs: tuple[str, ...]) -> dict:
    """Only the nodes the outputs depend on, so nodes left over from another backend don't run."""
    keep, todo = set(), list(outputs)
    while todo:
        node = todo.pop()
        if node not in keep:
            keep.add(node)
            todo += [value[0] for value in graph[node]["inputs"].values()
                     if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)]
    return {node: graph[node] for node in graph if node in keep}

def animate(
    directions: Path,
    motion: str,
    *,
    seed: int | None = None,
    draft: bool = False,
    scale: float = 1.0,
    every: int = 2,
    snap: bool = True,
    backend: str = "scail2",
    retries: int = 0,
    out: Path = Path("output"),
    on_event: Callable[[Event], None] | None = None,
) -> Path:
    if isinstance(every, bool) or not isinstance(every, int) or every < 1:
        raise ValueError("every must be a positive integer")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("scale must be a finite number greater than zero")
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {', '.join(BACKENDS)}")
    if backend in SEEDANCE and (draft or scale != 1.0):
        raise ValueError("--draft and --scale apply to SCAIL2 only; Seedance renders at its own resolution")
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
        # Replicate takes a 32-bit signed seed.
        seed = secrets.randbits(31 if backend in SEEDANCE else 32)
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
    if backend in SEEDANCE:
        # Seedance takes whole seconds of driving video at 24 fps, and replaces SCAIL2 from sampling to decoding.
        graph["4"]["inputs"]["frames"] = SEEDANCE_SECONDS * 24 + 1
        graph["700"] = {"class_type": "SpruteSeedance", "inputs": {
            "reference": ["489", 0], "driving": ["493", 0], "motion": ["601", 0], "model": SEEDANCE[backend],
            "seed": seed, "seconds": SEEDANCE_SECONDS, "retries": retries}}
        graph["592"]["inputs"]["image"] = ["700", 0]
        graph = reachable(graph, ("577",))
    if destination.is_file() and same_workflow(saved_workflow(destination), graph):
        report("completed", f"Animation unchanged: {destination}")
        return destination
    via = f" · {SEEDANCE[backend]} on Replicate" if backend in SEEDANCE else ""
    report("started", f"Animating {motion} from {motion_file.name} · seed {seed}{f' · scale {scale:g}' if scale != 1.0 else ''}{via}", timed=True)
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
