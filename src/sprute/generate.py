import json
import secrets
from collections.abc import Callable
from pathlib import Path
from sprute.comfy import run_workflow
from sprute.events import Event

WORKFLOW = Path("workflows/sprute-v2-generate-character.api.json")
TEMPLATE = Path("assets/sprute-v2-fill.png")

def generate(
    prompt: str,
    *,
    seed: int | None = None,
    out: Path = Path("output"),
    name: str | None = None,
    model_dirs: tuple[Path, ...] = (),
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
    graph["17"]["inputs"]["image"] = template.name
    graph["114"]["inputs"]["filename_prefix"] = "reference"
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if name is not None:
        if not name.strip() or name in (".", "..") or any(c in name for c in '/\\\0'):
            raise ValueError("Name must be a filename, without directory separators.")
        named_output = out / f"{name}.character.png"
        if named_output.exists() or named_output.is_symlink():
            raise FileExistsError(f"Character already exists: {named_output}")
    data = run_workflow(
        graph,
        outputs=("114",),
        model_dirs=model_dirs,
        extra_args=(
            "--input-directory", str(template.parent),
        ),
        on_log=lambda message: report("log", message),
    )["114"]
    index = 1
    while True:
        destination = out / (f"{name}.character.png" if name is not None else f"{index:04d}.character.png")
        try:
            target = destination.open("xb")
        except FileExistsError:
            if name is not None:
                raise FileExistsError(f"Character already exists: {destination}") from None
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
