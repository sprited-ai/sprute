from pathlib import Path
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from time import sleep
from collections import deque
import shutil
import subprocess
import sys

COMFY_VERSION = "0.37.0.1"
COMFY_INDEX_URL = "https://nodes.appmana.com/simple/"

@dataclass(frozen=True)
class SetupEvent:
    state: Literal["started", "completed"]
    message: str

def setup(
    workspace: Path,
    *,
    on_event: Callable[[SetupEvent], None] | None = None,
) -> Path:
    def report(
        state: Literal["started", "completed"],
        message: str,
    ) -> None:
        if on_event is not None:
            on_event(SetupEvent(state, message))
    report("started", "Preparing workspace")
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    report("completed", "Workspace ready")
    # Setup comfyUI
    report("started", f"Installing headless ComfyUI {COMFY_VERSION}")
    result = subprocess.run(
        [
            sys.executable, "-m", "pip",
            "install",
            "--extra-index-url", COMFY_INDEX_URL,
            f"comfyui=={COMFY_VERSION}",
        ],
        check=True,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"ComfyUI installation failed:\n{details}")
    report("completed", f"ComfyUI {COMFY_VERSION} installed")
    return workspace
