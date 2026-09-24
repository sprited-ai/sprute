from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Event:
    state: Literal["started", "completed", "progress", "log", "warning"]
    message: str
    timed: bool = False
