from pathlib import Path
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from time import sleep
from collections import deque
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
import json
from tempfile import TemporaryDirectory
from sprute.comfy import run_workflow

COMFY_VERSION = "0.37.0.1"
COMFY_INDEX_URL = "https://nodes.appmana.com/simple/"

@dataclass(frozen=True)
class SetupEvent:
    state: Literal["started", "completed", "log"]
    message: str

def setup(
    workspace: Path,
    *,
    on_event: Callable[[SetupEvent], None] | None = None,
    reinstall: bool = False,
) -> Path:
    def report(
        state: Literal["started", "completed", "log"],
        message: str,
    ) -> None:
        if on_event is not None:
            on_event(SetupEvent(state, message))

    # 1. Ensure Workspace
    report("started", "Preparing workspace")
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    report("completed", "Workspace ready")

    # 2. Setup ComfyUI
    if is_installed("comfyui") and not reinstall:
        report("completed", "ComfyUI already installed")
    else:
        action = "Reinstalling" if reinstall else "Installing"
        report("started", f"{action} headless ComfyUI {COMFY_VERSION}")
        command = [
            sys.executable, "-u", "-m", "pip",
            "install",
            "--progress-bar", "off",
            "--extra-index-url", COMFY_INDEX_URL,
            f"comfyui=={COMFY_VERSION}",
        ]
        if reinstall:
            command.append("--force-reinstall")
        recent_logs: deque[str] = deque(maxlen=20)
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        ) as process:
            assert process.stdout is not None
            try:
                for line in process.stdout:
                    message = line.rstrip("\r\n")
                    recent_logs.append(message)
                    report("log", message)
                returncode = process.wait()
            except BaseException:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise
        if returncode != 0:
            details = "\n".join(recent_logs)
            raise RuntimeError(f"ComfyUI installation failed:\n{details}")
        report("completed", f"ComfyUI {COMFY_VERSION} installed")

    # 3. Test Torch and GPU
    report("started", "Testing PyTorch and GPU")
    import torch
    device = (
        "cuda" if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available()
        else "cpu"
    )
    a = torch.ones((256, 256), device=device)
    result = (a @ a).cpu()
    torch.testing.assert_close(
        result,
        torch.full((256,256), 256.0),
    )
    report(
        "completed",
        f"PyTorch {torch.__version__} · {device} · matrix multiplication passed",
    )
    # 4. Try to run ComfyUI
    report("started", "Testing ComfyUI workflow")
    workflow = {
        "1": {
            "class_type": "EmptyImage",
            "inputs": {
                "width": 64,
                "height": 64,
                "batch_size": 1,
                "color": 0,
            },
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["1", 0],
                "filename_prefix": "sprute-setup-test",
            },
        },
    }
    with TemporaryDirectory(prefix="sprute-check-") as directory:
        temporary = Path(directory)
        workflow_path = temporary / "workflow.json"
        workflow_path.write_text(
            json.dumps(workflow),
            encoding="utf-8",
        )
        result = run_workflow(
            workflow_path,
            output=temporary / "output",
            on_log=lambda message: report("log", message),
            extra_args=(
                "--disable-all-custom-nodes",
                "--base-directory",
                str(temporary),
            )
        )
        image_path = Path(result["2"]["images"][0]["abs_path"])
        from PIL import Image
        with Image.open(image_path) as image:
            image.load()
            if image.format != "PNG" or image.size != (64, 64):
                raise RuntimeError("Unexpected ComfyUI test image")
    report("completed", "ComfyUI workflow verified")

    return workspace

def is_installed(package: str) -> bool:
    try:
        version(package)
        return True
    except PackageNotFoundError:
        return False
