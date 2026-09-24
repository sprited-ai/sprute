from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Event:
    state: Literal["started", "completed", "progress", "log", "warning", "image"]
    message: str
    timed: bool = False
