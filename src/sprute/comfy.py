import hashlib
import json
import os
import shutil
import subprocess
import sysconfig
from collections import deque
from importlib.metadata import distribution
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from sprute.config import get_models_directory
from sprute.gpu import monitor_vram
from sprute.events import Event

def input_name(path: Path) -> str:
    """Name an input by its content so the saved workflow identifies it exactly."""
    return content_name(path.read_bytes(), path.suffix)

def content_name(content: bytes, suffix: str) -> str:
    return hashlib.sha256(content).hexdigest() + suffix


def custom_nodes_path() -> Path:
    """Locate the node checkout directory without importing ComfyUI."""
    return Path(distribution("comfyui").locate_file("comfy/custom_nodes")).resolve()

def run_workflow(
    workflow: dict,
    *,
    input_files: dict[str, Path | bytes] | None = None,
    output_node_ids: tuple[str, ...],
    on_event: Callable[[Event], None] | None = None,
) -> dict[str, bytes]:
    """Run an API workflow and return the first saved image or GLB of each output node, by node id."""
    def emit(event: Event) -> None:
        if on_event is not None:
            on_event(event)

    executable = Path(sysconfig.get_path("scripts")) / (
        "comfyui.exe" if os.name == "nt" else "comfyui"
    )
    models_directory = get_models_directory().resolve(strict=True)
    if not models_directory.is_dir():
        raise NotADirectoryError(f"Not a models directory: {models_directory}")
    with (
        TemporaryDirectory(prefix="sprute-comfy-") as workspace,
        TemporaryFile(mode="w+", encoding="utf-8") as result,
    ):
        workflow_path = Path(workspace) / "workflow.json"
        output_directory = Path(workspace) / "output"
        input_directory = Path(workspace) / "input"
        input_directory.mkdir()
        # The workflow refers to input files by the name they are copied under.
        for name, source in (input_files or {}).items():
            if isinstance(source, bytes):
                (input_directory / name).write_bytes(source)
            else:
                shutil.copyfile(source, input_directory / name)
        workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
        command = [
            str(executable),
            "run-workflow",
            str(workflow_path),
            "--input-directory",
            str(input_directory),
            "--output-directory",
            str(output_directory),
            "--models-directory",
            str(models_directory),
            "--disable-progress",
        ]
        command.extend(["--base-directory", workspace])
        command.extend(["--base-paths", str(custom_nodes_path().parent)])
        # Sprute's own nodes are in this repository's custom_nodes folder.
        command.extend(["--base-paths", str(Path.cwd())])
        recent_logs: deque[str] = deque(maxlen=20)
        with subprocess.Popen(
            command,
            cwd=workspace,
            stdout=result,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        ) as process, monitor_vram(
            process.pid,
            (lambda message: emit(Event("vram", message))) if on_event is not None else None,
        ):
            assert process.stderr is not None
            try:
                for line in process.stderr:
                    message = line.rstrip("\r\n")
                    recent_logs.append(message)
                    emit(Event("log", message))
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
            details = "\n".join(recent_logs).strip()
            if not details:
                result.seek(0)
                details = result.read()[-8000:].strip()
            raise RuntimeError(
                f"ComfyUI exited with code {returncode}.\n"
                f"{details or 'No error output was produced.'}"
            )
        result.seek(0)
        # Some custom nodes print to stdout before Comfy emits its JSON result.
        saved = None
        for line in result:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                emit(Event("log", line.rstrip("\r\n")))
                continue
            if isinstance(value, dict):
                saved = value
            else:
                emit(Event("log", line.rstrip("\r\n")))
        if saved is None:
            raise RuntimeError("ComfyUI exited successfully but returned no JSON result.")
        return {
            node_id: _output_path(saved, node_id, output_directory=output_directory).read_bytes()
            for node_id in output_node_ids
        }


def _output_path(result: dict, node_id: str, *, output_directory: Path) -> Path:
    """Resolve the first saved image or GLB."""
    files = result[node_id].get("images") or result[node_id].get("3d")
    if not files:
        raise ValueError(f"ComfyUI node {node_id} returned no saved image or GLB")
    saved = files[0]
    path = (
        Path(saved["abs_path"])
        if saved.get("abs_path")
        else output_directory / saved.get("subfolder", "") / saved["filename"]
    )
    if not path.is_file():
        raise FileNotFoundError(f"ComfyUI output not found: {path}")
    return path


def saved_workflow(path: Path) -> dict | None:
    """Read the API workflow ComfyUI embeds in a saved PNG or animated WebP."""
    from PIL import Image
    try:
        with Image.open(path) as image:
            if "prompt" in image.info:
                return json.loads(image.info["prompt"])
            # SaveAnimatedWEBP stores it in EXIF 0x0110 as "prompt:{...}".
            prompt = image.getexif().get(0x0110, "")
            return json.loads(prompt.removeprefix("prompt:")) if prompt.startswith("prompt:") else None
    except (OSError, ValueError):
        return None


def same_workflow(saved: dict | None, workflow: dict) -> bool:
    """Compare what runs; ComfyUI adds bookkeeping such as is_changed when saving."""
    def runnable(nodes: dict) -> dict:
        return {node_id: (node.get("class_type"), node.get("inputs")) for node_id, node in nodes.items()}
    return saved is not None and runnable(saved) == runnable(workflow)
