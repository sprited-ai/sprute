import json
import secrets
from collections.abc import Callable
from pathlib import Path
from sprute.comfy import input_name, run_workflow, same_workflow, saved_workflow
from sprute.events import Event

WORKFLOW = Path("workflows/sprute-render-motion.api.json")
GENERATE_WORKFLOW = Path("workflows/sprute-kimodo-to-glb.api.json")
MOTIONS = Path("motions")

def motions() -> list[str]:
    return sorted(path.relative_to(MOTIONS).with_suffix("").as_posix() for path in MOTIONS.rglob("*.glb"))

def find_motion(motion: str) -> Path:
    """The motion's GLB, by path or by name in motions/."""
    path = Path(motion).expanduser()
    if path.is_file():
        if path.suffix.lower() == ".webp":
            raise ValueError("WebP driving videos are no longer supported; give a GLB motion")
        if path.suffix.lower() != ".glb":
            raise ValueError("A motion file must be a GLB")
        return path
    path = MOTIONS / f"{motion}.glb"
    if path.is_file():
        return path
    raise ValueError(f"Unknown motion {motion!r}; choose one of: {', '.join(motions())}")

def generate_motion(
    prompt: str,
    destination: Path,
    *,
    seed: int | None = None,
    duration: float = 3.5,
    steps: int = 100,
    on_event: Callable[[Event], None] | None = None,
) -> Path:
    """Generate a motion-only GLB through the Kimodo workflow."""
    if not prompt.strip():
        raise ValueError("A motion prompt is required")
    if not 0.5 <= duration <= 10 or not 10 <= steps <= 500:
        raise ValueError("Use 0.5–10 seconds and 10–500 diffusion steps")
    if seed is not None and not 0 <= seed < 2**32:
        raise ValueError("Kimodo seed must be a 32-bit unsigned integer")
    destination = destination.expanduser().resolve()
    if destination.suffix.lower() != ".glb":
        raise ValueError("Motion output must be a .glb file")
    if destination.exists():
        raise FileExistsError(f"Motion already exists: {destination}")
    seed = secrets.randbits(32) if seed is None else seed
    graph = json.loads(GENERATE_WORKFLOW.read_text())
    graph["2"]["inputs"]["prompt"] = prompt
    graph["3"]["inputs"].update(duration=duration, seed=seed, diffusion_steps=steps)
    if on_event:
        on_event(Event("started", f"Generating motion · seed {seed}", timed=True))
    data = run_workflow(graph, output_node_ids=("6",), on_event=on_event)["6"]
    if data[:4] != b"glTF":
        raise ValueError("Kimodo workflow did not return a GLB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        output.write(data)
    if on_event:
        on_event(Event("completed", f"Motion saved: {destination}"))
    return destination


def render_motion(
    motion: Path,
    *,
    cell_width: int = 256,
    cell_height: int = 256,
    on_event: Callable[[Event], None] | None = None,
) -> bytes:
    """Render a GLB in eight directions, reusing its .cached.webp when the inputs match."""
    def report(state, message, *, timed=False):
        if on_event is not None:
            on_event(Event(state, message, timed=timed))
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["1"]["inputs"]["motion"] = input_name(motion)
    graph["2"]["inputs"].update(cell_width=cell_width, cell_height=cell_height)
    cache = motion.with_suffix(".cached.webp")
    if cache.is_file() and same_workflow(saved_workflow(cache), graph):
        report("completed", f"Using cached motion: {cache}")
        return cache.read_bytes()
    report("started", f"Rendering {motion.name}", timed=True)
    data = run_workflow(
        graph,
        input_files={graph["1"]["inputs"]["motion"]: motion},
        output_node_ids=("4",),
        on_event=on_event,
    )["4"]
    cache.write_bytes(data)
    report("completed", f"Rendered {motion.name}")
    return data
