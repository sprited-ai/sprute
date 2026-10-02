import json
from io import BytesIO
from collections.abc import Callable
from pathlib import Path
from PIL import Image
from sprute.comfy import input_name, run_workflow
from sprute.events import Event

WORKFLOW = Path("workflows/sprute-render-motion.api.json")
MOTIONS = Path("motions")
MINIMUM_FRAMES = 5

def motions() -> list[str]:
    return sorted({path.stem for suffix in ("webp", "glb") for path in MOTIONS.glob(f"*.{suffix}")})

def find_motion(motion: str) -> Path:
    """The motion's driving video if there is one, otherwise its GLB."""
    for suffix in ("webp", "glb"):
        path = MOTIONS / f"{motion}.{suffix}"
        if path.is_file():
            return path
    raise ValueError(f"Unknown motion {motion!r}; choose one of: {', '.join(motions())}")

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
    on_event: Callable[[Event], None] | None = None,
) -> bytes:
    """Render a GLB the way animate sees it: Template-kun in eight directions, as an animated WebP."""
    def report(state, message, *, timed=False):
        if on_event is not None:
            on_event(Event(state, message, timed=timed))
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["1"]["inputs"]["motion"] = input_name(motion)
    report("started", f"Rendering {motion.name}", timed=True)
    data = run_workflow(
        graph,
        input_files={input_name(motion): motion},
        output_node_ids=("4",),
        on_event=on_event,
    )["4"]
    report("completed", f"Rendered {motion.name}")
    return data


def generate_motion(prompt: str, *, seed: int, out: Path,
                    on_event: Callable[[Event], None] | None = None) -> Path:
    """Generate and render one finite Kimodo clip with the standard mannequin."""
    if not prompt.strip():
        raise ValueError("A motion prompt is required")
    graph = json.loads(Path("workflows/sprute-kimodo-motion.api.json").read_text())
    graph["2"]["inputs"]["prompt"] = prompt
    graph["3"]["inputs"]["seed"] = seed
    if on_event:
        on_event(Event("started", "Generating Kimodo motion", timed=True))
    data = run_workflow(graph, output_node_ids=("8",), on_event=on_event)["8"]
    out.mkdir(parents=True, exist_ok=True)
    destination = out / "sprite.driving.webp"
    destination.write_bytes(data)
    if on_event:
        on_event(Event("completed", f"Driving motion saved: {destination}"))
    return destination
