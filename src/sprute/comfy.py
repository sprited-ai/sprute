import json
import os
import subprocess
import sysconfig
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryFile

def run_workflow(
    workflow: Path,
    *,
    output: Path,
    on_log: Callable[[str], None],
    extra_args: tuple[str, ...] = (),
) -> dict:
    executable = Path(sysconfig.get_path("scripts")) / (
        "comfyui.exe" if os.name == "nt" else "comfyui"
    )
    command = [
        str(executable),
        "run-workflow",
        str(workflow.resolve()),
        "--output-directory",
        str(output.resolve()),
        "--disable-progress",
        *extra_args,
    ]
    with TemporaryFile(mode="w+", encoding="utf-8") as result:
        with subprocess.Popen(
            command,
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
                    on_log(line.rstrip("\r\n"))
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
            raise RuntimeError(
                f"ComfyUI exited with code {returncode}. "
                "See the logs above."
            )
        result.seek(0)
        return json.load(result)
    