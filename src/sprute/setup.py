from pathlib import Path
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from time import perf_counter
from collections import deque
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
import json
from tempfile import TemporaryDirectory
from sprute.comfy import custom_nodes_path, run_workflow

COMFY_VERSION = "0.37.0.1"
COMFY_INDEX_URL = "https://nodes.appmana.com/simple/"
CUSTOM_NODES = {
    "ComfyUI-KJNodes": {
        "repository": "https://github.com/kijai/ComfyUI-KJNodes.git",
        "revision": "d3cfe21625e5170126ce06fbfcfe1d88108688c3",
    },
    "ComfyUI-RMBG": {
        "repository": "https://github.com/kndlt/ComfyUI-RMBG.git",
        "revision": "7f02fab3f33aee806002c9b349cc9ea763f4d2e7",
    },
    "comfyui-fitsize": {
        "repository": "https://github.com/bronkula/comfyui-fitsize.git",
        "revision": "dff0221df4859a6de4a7ef26d5a3900a153818e1",
    },
    "ComfyUI-Custom-Scripts": {
        "repository": "https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git",
        "revision": "609f3afaa74b2f88ef9ce8d939626065e3247469",
    },
    "ComfyUI-VideoHelperSuite": {
        "repository": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        "revision": "4d907bee61e92c2e65af3bd6383a4e4d356126d1",
    },
}

@dataclass(frozen=True)
class SetupEvent:
    state: Literal["started", "completed", "log", "warning"]
    message: str
    timed: bool = False

class Reporter(Protocol):
    def __call__(
        self,
        state: Literal["started", "completed", "log", "warning"],
        message: str,
        *,
        timed: bool = False,
    ) -> None: ...

def setup(
    *,
    on_event: Callable[[SetupEvent], None] | None = None,
    reinstall: bool = False,
) -> None:
    def report(
        state: Literal["started", "completed", "log", "warning"],
        message: str,
        *,
        timed: bool = False,
    ) -> None:
        if on_event is not None:
            on_event(SetupEvent(state, message, timed=timed))

    report("completed", f"Python {sys.version.split()[0]}")
    setup_comfy(report=report, reinstall=reinstall)
    setup_custom_nodes(report=report, reinstall=reinstall)
    check_torch(report=report)
    check_comfy_workflow(report=report)

def setup_comfy(*, report: Reporter, reinstall: bool = False) -> None:
    if is_installed("comfyui") and not reinstall:
        report("completed", f"ComfyUI {version('comfyui')}")
    else:
        action = "Reinstalling" if reinstall else "Installing"
        report("started", f"{action} headless ComfyUI {COMFY_VERSION}", timed=True)
        command = pip_install_command(reinstall=reinstall) + [
            "--extra-index-url", COMFY_INDEX_URL,
            f"comfyui=={COMFY_VERSION}",
        ]
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

def setup_custom_nodes(*, report: Reporter, reinstall: bool = False) -> None:
    node_directory = custom_nodes_path()
    node_directory.mkdir(parents=True, exist_ok=True)
    report("log", f"Custom nodes: {node_directory}")
    report("started", "Installing ComfyUI custom nodes", timed=True)
    for name, node in CUSTOM_NODES.items():
        destination = node_directory / name
        revision = node["revision"]
        installed = destination / ".git" / "sprute-installed-revision"
        current_revision = None
        if (destination / ".git").is_dir():
            current = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=destination,
                capture_output=True,
                text=True,
            )
            if current.returncode == 0:
                current_revision = current.stdout.strip()
        if (
            not reinstall
            and current_revision == revision
            and installed.is_file()
            and installed.read_text().strip() == revision
        ):
            report("log", f"{name} already installed")
            continue
        report("log", f"Preparing {name}")
        if not destination.exists():
            run(["git", "init", str(destination)], report=report)
            run(
                ["git", "remote", "add", "origin", node["repository"]],
                cwd=destination,
                report=report,
            )
        elif not (destination / ".git").is_dir():
            raise RuntimeError(
                f"{destination} exists but is not a Git checkout"
            )
        # A failed install must be retried on the next setup run.
        installed.unlink(missing_ok=True)
        if current_revision != revision or reinstall:
            run(
                ["git", "fetch", "--depth", "1", "origin", revision],
                cwd=destination,
                report=report,
            )
            run(
                ["git", "checkout", "--detach", revision],
                cwd=destination,
                report=report,
            )
        requirements = destination / "requirements.txt"
        if requirements.is_file():
            report("log", f"Installing {name} dependencies")
            run(
                pip_install_command() + ["-r", str(requirements)],
                cwd=destination,
                report=report,
            )
        installed.write_text(revision + "\n")
        report("log", f"{name} installed")
    report("completed", "ComfyUI custom nodes installed")

def check_torch(*, report: Reporter) -> None:
    report("started", "Testing PyTorch and GPU")
    import warnings
    warnings.filterwarnings(
        "ignore",
        message=r"(?s)Warning only once for all operators.*Overriding.*dispatch key: MPS",
        category=UserWarning,
        module=r"torch\.library",
    )
    import torch
    device = (
        "cuda" if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available()
        else "cpu"
    )
    if device != "cuda":
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi is not None:
            try:
                probe = subprocess.run(
                    [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                report("warning", f"NVIDIA GPU detection unavailable: {error}")
            else:
                if probe.returncode != 0:
                    details = probe.stderr.strip() or probe.stdout.strip()
                    report("warning", f"NVIDIA GPU detection failed: {details or probe.returncode}")
                elif probe.stdout.strip():
                    names = ", ".join(probe.stdout.strip().splitlines())
                    reason = (
                        "This PyTorch build has no CUDA support."
                        if torch.version.cuda is None
                        else "Check the NVIDIA driver, device permissions, and CUDA_VISIBLE_DEVICES."
                    )
                    report(
                        "warning",
                        f"NVIDIA GPU detected ({names}), but PyTorch cannot use CUDA. "
                        f"{reason} Selected device: {device}.",
                    )
                else:
                    report("log", "nvidia-smi returned no GPU names; no NVIDIA GPU confirmed.")
    report(
        "completed",
        f"PyTorch {torch.__version__}",
    )
    if device == "cuda":
        name = torch.cuda.get_device_name()
        free, total = torch.cuda.mem_get_info()
        report("completed", f"Device: cuda · {name}")
        report(
            "completed",
            f"VRAM: {total / 1024**3:.1f} GiB total"
            f" · {free / 1024**3:.1f} GiB free",
        )
    elif device == "mps":
        chip = subprocess.check_output(
            ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
            text=True,
        ).strip()
        memory_bytes = int(subprocess.check_output(
            ["/usr/sbin/sysctl", "-n", "hw.memsize"],
            text=True,
        ))
        memory_gb = memory_bytes / 1024**3
        report(
            "completed",
            f"Device: mps · {chip} · {memory_gb:.0f} GB unified memory",
        )
    else:
        report("completed", f"Device: {device}")
    matrix_size = 2048
    iterations = 20

    def synchronize() -> None:
        if device == "cuda":
            torch.cuda.synchronize()
        elif device == "mps":
            torch.mps.synchronize()

    for label, dtype in (
        ("FP32", torch.float32),
        ("FP16", torch.float16),
        ("BF16", torch.bfloat16),
    ):
        report("started", f"Testing {label} matrix multiplication")
        try:
            a = torch.ones((matrix_size, matrix_size), device=device, dtype=dtype)
            for _ in range(5):
                result = a @ a
            synchronize()

            started = perf_counter()
            for _ in range(iterations):
                result = a @ a
            synchronize()
            average_ms = (perf_counter() - started) * 1000 / iterations
        except (RuntimeError, TypeError, NotImplementedError) as error:
            # Unsupported dtype/backend combinations may be skipped; other
            # failures (including out-of-memory) must remain setup errors.
            message = str(error).lower()
            if not any(term in message for term in (
                "not implemented", "not supported", "does not support", "unsupported",
            )):
                raise
            report("warning", f"{label} unavailable on {device}: {error}")
            continue

        torch.testing.assert_close(
            result.cpu(),
            torch.full((matrix_size, matrix_size), float(matrix_size), dtype=dtype),
        )
        report(
            "completed",
            f"Matrix Multiplication ({label}): {average_ms:.2f} ms",
        )
        del a, result

def check_comfy_workflow(*, report: Reporter) -> None:
    report("started", "Testing ComfyUI workflow", timed=True)
    workflow = {
        "1": {
            "class_type": "EmptyImage",
            "inputs": {
                "width": 64,
                "height": 64,
                "batch_size": 2,
                "color": 0,
            },
        },
        "2": {
            "class_type": "ImageConcatFromBatch",
            "inputs": {
                "images": ["1", 0],
                "num_columns": 2,
                "match_image_size": False,
                "max_resolution": 4096,
            },
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["2", 0],
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
            on_log=lambda message: report("log", message)
        )
        image_path = Path(result["3"]["images"][0]["abs_path"])
        from PIL import Image
        with Image.open(image_path) as image:
            image.load()
            if image.format != "PNG" or image.size != (128, 64):
                raise RuntimeError(
                    f"Unexpected ComfyUI test image: {image.format} {image.size}; "
                    "expected PNG (128, 64)"
                )
    report("completed", "ComfyUI workflow verified")

def run(
    command: list[str],
    *,
    report: Reporter,
    cwd: Path | None = None
) -> None:
    recent_logs: deque[str] = deque(maxlen=20)
    with subprocess.Popen(
        command,
        cwd=cwd,
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
        raise RuntimeError(
            f"{command[0]} failed ({returncode}):\n"
            + "\n".join(recent_logs)
        )

def is_installed(package: str) -> bool:
    try:
        version(package)
        return True
    except PackageNotFoundError:
        return False

def is_uv_venv() -> bool:
    config = Path(sys.prefix) / "pyvenv.cfg"
    return config.is_file() and any(
        line.partition("=")[0].strip() == "uv"
        for line in config.read_text().splitlines()
    )

def pip_install_command(*, reinstall: bool = False) -> list[str]:
    """Always install into the Python environment running Sprute."""
    if is_uv_venv():
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError(
                "This environment was created with uv, but uv is not on PATH. "
                "Make uv available, then run sprute setup again."
            )
        command = [uv, "pip", "install", "--python", sys.executable, "--no-progress"]
        if reinstall:
            command.append("--reinstall")
        return command

    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"pip is unavailable in this Python environment: {sys.executable}\n"
            f"{details}\n"
            "Install pip in this environment, then run sprute setup again:\n"
            f'uv pip install --python "{sys.executable}" pip'
        )
    command = [sys.executable, "-u", "-m", "pip", "install", "--progress-bar", "off"]
    if reinstall:
        command.append("--force-reinstall")
    return command
