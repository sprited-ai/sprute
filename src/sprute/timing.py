"""The frame rate to render a motion at, so a loop's cycle is a whole number of saved frames."""
import json
import struct
from dataclasses import dataclass
from pathlib import Path

FPS = 24.0


@dataclass(frozen=True)
class Plan:
    cycle: int  # frames one loop takes at 24 fps, a multiple of every
    fps: float  # frame rate that fits the motion's cycle into those frames
    scale: float  # how much longer the motion plays at 24 fps than it lasts


def plan(seconds: float, loop: bool, every: int) -> Plan:
    if not loop:
        return Plan(round(seconds * FPS), FPS, 1.0)
    # Snap the cycle to a multiple of every frames, so keeping every Nth leaves whole steps.
    cycle = every * max(1, round(seconds * FPS / every))
    return Plan(cycle, cycle / seconds, cycle / (seconds * FPS))


def glb_cycle(path: Path) -> tuple[float, bool]:
    """Seconds and whether it loops, for the first animation in a GLB."""
    data = path.read_bytes()
    length = struct.unpack("<I", data[12:16])[0]
    document = json.loads(data[20:20 + length])
    animation = document["animations"][0]
    inputs = [document["accessors"][sampler["input"]] for sampler in animation["samplers"]]
    seconds = max(i["max"][0] for i in inputs) - min(i["min"][0] for i in inputs)
    # Retargeting reads a missing loop flag the same way.
    return seconds, bool(animation.get("extras", {}).get("loop", True))
