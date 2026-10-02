"""Bound inference and terminate its process group on timeout or cancellation."""
import os
import signal
import subprocess


def run_bounded(command, *, timeout, cwd):
    process = subprocess.Popen(command, cwd=cwd, start_new_session=True)
    try:
        code = process.wait(timeout=timeout)
        if code:
            raise RuntimeError(f"Sprute worker exited with code {code}. See the logs above.")
    except BaseException:
        # Comfy and any descendants share this worker's group. Killing only the
        # immediate child could leave an inference process consuming GPU memory.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
