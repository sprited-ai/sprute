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

def input_name(path: Path) -> str:
    """Name an input by its content so the saved workflow identifies it exactly."""
    return hashlib.sha256(path.read_bytes()).hexdigest() + path.suffix


def custom_nodes_path() -> Path:
    """Locate the node checkout directory without importing ComfyUI."""
    return Path(distribution("comfyui").locate_file("comfy/custom_nodes")).resolve()

def run_workflow(
    workflow: dict,
    *,
    input_files: dict[str, Path] | None = None,
    output_node_ids: tuple[str, ...],
    on_log: Callable[[str], None],
) -> dict[str, bytes]:
    """Run an API workflow and return the first saved image of each output node, by node id."""
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
        for name, path in (input_files or {}).items():
            shutil.copyfile(path, input_directory / name)
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
        ) as process:
            assert process.stderr is not None
            try:
                for line in process.stderr:
                    message = line.rstrip("\r\n")
                    recent_logs.append(message)
                    on_log(message)
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
                on_log(line.rstrip("\r\n"))
                continue
            if isinstance(value, dict):
                saved = value
            else:
                on_log(line.rstrip("\r\n"))
        if saved is None:
            raise RuntimeError("ComfyUI exited successfully but returned no JSON result.")
        return {
            node_id: _output_path(saved, node_id, output_directory=output_directory).read_bytes()
            for node_id in output_node_ids
        }


def _output_path(result: dict, node_id: str, *, output_directory: Path) -> Path:
    """Resolve the first saved image, including animated WebP outputs."""
    saved = result[node_id]["images"][0]
    path = (
        Path(saved["abs_path"])
        if saved.get("abs_path")
        else output_directory / saved.get("subfolder", "") / saved["filename"]
    )
    if not path.is_file():
        raise FileNotFoundError(f"ComfyUI output not found: {path}")
    return path
