import json
from pathlib import Path
from sprute.comfy import input_name, run_workflow

WORKFLOW = Path("workflows/sprute-check-animation.api.json")


def check(animation: Path, directions: Path, *, directions_drawn: int = 8) -> dict:
    """Measure each drawn direction of an animation strip against the character's directions strip.
    Returns {"directions": {name: per-frame measurements}, "verdict": {name: {"pass", "reasons"}}}."""
    animation = animation.expanduser().resolve(strict=True)
    directions = directions.expanduser().resolve(strict=True)
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    animation_name, directions_name = input_name(animation), input_name(directions)
    graph["1"]["inputs"]["image"] = animation_name
    graph["2"]["inputs"]["image"] = directions_name
    if directions_drawn != 8:
        graph["4"]["inputs"]["directions"] = str(directions_drawn)
    data = run_workflow(
        graph,
        input_files={animation_name: animation, directions_name: directions},
        output_node_ids=("4",),
    )["4"]
    return json.loads(data)
