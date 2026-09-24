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
    workflow: Path,
    *,
    output: Path,
    on_log: Callable[[str], None],
    paths_config: Path | None = None,
    extra_args: tuple[str, ...] = (),
) -> dict:
    executable = Path(sysconfig.get_path("scripts")) / (
        "comfyui.exe" if os.name == "nt" else "comfyui"
    )
    # Use the checkout's config when present; callers elsewhere can pass a path.
    if paths_config is None:
        local_config = Path("comfy-paths.yaml")
        if local_config.is_file():
            paths_config = local_config
    command = [
        str(executable),
        "run-workflow",
        str(workflow.resolve()),
        "--output-directory",
        str(output.resolve()),
        "--disable-progress",
        *extra_args,
    ]
    if paths_config is not None:
        command.extend([
            "--extra-model-paths-config",
            str(paths_config.resolve(strict=True)),
        ])
    with (
        TemporaryDirectory(prefix="sprute-comfy-") as workspace,
        TemporaryFile(mode="w+", encoding="utf-8") as result,
    ):
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
        outputs = None
        for line in result:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                on_log(line.rstrip("\r\n"))
                continue
            if isinstance(value, dict):
                outputs = value
            else:
                on_log(line.rstrip("\r\n"))
        if outputs is None:
            raise RuntimeError("ComfyUI exited successfully but returned no JSON result.")
        return outputs
    
