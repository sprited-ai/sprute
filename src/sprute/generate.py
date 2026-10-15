import json
import secrets
from collections.abc import Callable
from pathlib import Path
from sprute.comfy import input_name, run_workflow
from sprute.events import Event

WORKFLOW = Path("workflows/sprute-generate-character.api.json")
TEMPLATE = Path("assets/sprute-fill.png")

def generate(
    prompt: str,
    *,
    seed: int | None = None,
    out: Path = Path("output"),
    name: str | None = None,
    on_event: Callable[[Event], None] | None = None,
) -> Path:
    def report(state, message, *, timed=False):
        if on_event is not None:
            on_event(Event(state, message, timed=timed))
    if seed is None:
        seed = secrets.randbits(32)
    report("started", f"Generating character · seed {seed}", timed=True)
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph["203"]["inputs"]["text"] = prompt
    graph["207"]["inputs"]["seed"] = seed
    template = TEMPLATE.resolve(strict=True)
    template_name = input_name(template)
    graph["17"]["inputs"]["image"] = template_name
    graph["114"]["inputs"]["filename_prefix"] = "reference"
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if name is not None:
        if not name.strip() or name in (".", "..") or any(c in name for c in '/\\\0'):
            raise ValueError("Name must be a filename, without directory separators.")
    data = run_workflow(
        graph,
        input_files={template_name: template},
        output_node_ids=("114",),
        on_event=on_event,
    )["114"]
    index = 1
    while True:
        output_name = name if index == 1 else f"{name}-{index}"
        destination = out / (f"{output_name}.character.png" if name is not None else f"{index:04d}.character.png")
        try:
            target = destination.open("xb")
        except FileExistsError:
            index += 1
            continue
        try:
            with target:
                target.write(data)
        except BaseException:
            destination.unlink()
            raise
        break
    report("completed", f"Character saved: {destination} · seed {seed}")
    return destination
