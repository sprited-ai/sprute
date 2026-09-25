import json
import os
import subprocess
import sysconfig
from collections import deque
from importlib.metadata import distribution
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile

def custom_nodes_path() -> Path:
    """Locate the node checkout directory without importing ComfyUI."""
    return Path(distribution("comfyui").locate_file("comfy/custom_nodes")).resolve()

def run_workflow(
    graph: dict,
    *,
    outputs: tuple[str, ...],
    on_log: Callable[[str], None],
    model_dirs: tuple[Path, ...] | None = None,
    extra_args: tuple[str, ...] = (),
) -> dict[str, bytes]:
    """Run a workflow and return the first saved image of each requested node."""
    executable = Path(sysconfig.get_path("scripts")) / (
        "comfyui.exe" if os.name == "nt" else "comfyui"
    )
    # None is used by the model-free setup check; an empty tuple selects ./models.
    if model_dirs is not None:
        model_dirs = tuple(
            path.expanduser().resolve(strict=True)
            for path in (model_dirs or (Path("models"),))
        )
        for path in model_dirs:
            if not path.is_dir():
                raise NotADirectoryError(f"Not a model directory: {path}")
    with (
        TemporaryDirectory(prefix="sprute-comfy-") as workspace,
        TemporaryFile(mode="w+", encoding="utf-8") as result,
    ):
        workflow = Path(workspace) / "workflow.json"
        output = Path(workspace) / "output"
        workflow.write_text(json.dumps(graph), encoding="utf-8")
        command = [
            str(executable),
            "run-workflow",
            str(workflow),
            "--output-directory",
            str(output),
            "--disable-progress",
            *extra_args,
        ]
        if model_dirs:
            command.extend(["--models-directory", str(model_dirs[0])])
        if model_dirs and len(model_dirs) > 1:
            # Additional roots use the same folder structure; no files are moved.
            categories = ("checkpoints", "diffusion_models", "text_encoders", "clip_vision", "vae", "loras")
            extra_paths = Path(workspace) / "model-paths.yaml"
            extra_paths.write_text(json.dumps({
                f"sprute_{index}": {
                    "base_path": str(root),
                    **{category: category for category in categories},
                }
                for index, root in enumerate(model_dirs)
            }), encoding="utf-8")
            command.extend(["--extra-model-paths-config", str(extra_paths)])
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
            node_id: _output_path(saved, node_id, output=output).read_bytes()
            for node_id in outputs
        }


def _output_path(result: dict, node_id: str, *, output: Path) -> Path:
    """Resolve the first saved image, including animated WebP outputs."""
    saved = result[node_id]["images"][0]
    path = (
        Path(saved["abs_path"])
        if saved.get("abs_path")
        else output / saved.get("subfolder", "") / saved["filename"]
    )
    if not path.is_file():
        raise FileNotFoundError(f"ComfyUI output not found: {path}")
    return path
