"""How many frames of a motion to render and keep, so a loop wraps without a jump or a short step."""
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

FPS = 24.0
# SCAIL2 works on 4n + 1 frames; 81 is the length it is used at.
FRAMES = 81


@dataclass(frozen=True)
class Plan:
    frames: int  # driving video length
    fps: float  # driving video frame rate
    keep: int  # generated frames to keep before every Nth is taken
    scale: float  # how much longer the kept frames play at 24 fps than the motion lasts


def plan(seconds: float, loop: bool, every: int) -> Plan:
    if not loop:
        return Plan(FRAMES, FPS, FRAMES, 1.0)
    # One cycle, snapped to a multiple of every frames so the wrap is a whole step.
    keep = every * max(1, round(seconds * FPS / every))
    frames = max(FRAMES, 4 * math.ceil((keep - 1) / 4) + 1)
    return Plan(frames, keep / seconds, keep, keep / (seconds * FPS))


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
