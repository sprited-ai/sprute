import json
import secrets
from io import BytesIO
from collections.abc import Callable
from pathlib import Path
from PIL import Image
from sprute.comfy import input_name, run_workflow
from sprute.events import Event

WORKFLOW = Path("workflows/sprute-render-motion.api.json")
GENERATE_WORKFLOW = Path("workflows/sprute-kimodo-to-glb.api.json")
MOTIONS = Path("motions")
MINIMUM_FRAMES = 5

def motions() -> list[str]:
    return sorted({path.relative_to(MOTIONS).with_suffix("").as_posix()
                   for suffix in ("webp", "glb") for path in MOTIONS.rglob(f"*.{suffix}")})

def find_motion(motion: str) -> Path:
    """The motion's driving video if there is one, otherwise its GLB."""
    path = Path(motion).expanduser()
    if path.is_file():
        if path.suffix.lower() not in (".glb", ".webp"):
            raise ValueError("A motion file must be .glb or .webp")
        return path
    for suffix in ("webp", "glb"):
        path = MOTIONS / f"{motion}.{suffix}"
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


def check_driving_video(video: bytes, name: str, directions: Path) -> None:
    """A driving video is an eight-direction animation of the same size as the directions image."""
    with Image.open(directions) as image:
        size = image.size
    with Image.open(BytesIO(video)) as image:
        frames = getattr(image, "n_frames", 1)
        if image.size != size:
            raise ValueError(f"{name} is {image.size[0]}x{image.size[1]}; it must be {size[0]}x{size[1]}, like {directions.name}")
        # SCAIL2 works on 4n+1 frames and drops up to three at the end to get there.
        if frames < MINIMUM_FRAMES:
            raise ValueError(f"{name} has {frames} frames; it must have at least {MINIMUM_FRAMES}")
        # An alpha channel alone is not enough: the first frame must have pixels that are see-through.
        if image.convert("RGBA").getchannel("A").getextrema()[0] == 255:
            raise ValueError(f"{name} has no transparency; the background must be transparent")

def render_motion(
    motion: Path,
    *,
    cell_width: int = 192,
    cell_height: int = 256,
    on_event: Callable[[Event], None] | None = None,
) -> bytes:
    """Render a GLB the way animate sees it: Template-kun in eight directions, as an animated WebP."""
    def report(state, message, *, timed=False):
        if on_event is not None:
            on_event(Event(state, message, timed=timed))
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["1"]["inputs"]["motion"] = input_name(motion)
    graph["2"]["inputs"].update(cell_width=cell_width, cell_height=cell_height)
    report("started", f"Rendering {motion.name}", timed=True)
    data = run_workflow(
        graph,
        input_files={input_name(motion): motion},
        output_node_ids=("4",),
        on_event=on_event,
    )["4"]
    report("completed", f"Rendered {motion.name}")
    return data
