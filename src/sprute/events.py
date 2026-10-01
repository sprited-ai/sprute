from dataclasses import dataclass
from typing import Literal

EventState = Literal["started", "completed", "progress", "log", "warning", "image", "vram"]

@dataclass(frozen=True)
class Event:
    state: EventState
    message: str
    timed: bool = False
