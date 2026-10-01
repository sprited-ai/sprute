"""Optional NVIDIA process-memory monitoring, without importing PyTorch."""
from collections.abc import Callable
from contextlib import contextmanager
from threading import Event, Thread


@contextmanager
def monitor_vram(pid: int, on_update: Callable[[str], None] | None):
    """Sample this process once per second; unavailable telemetry stays hidden."""
    if on_update is None:
        yield
        return
    try:
        import pynvml
    except ImportError:
        yield
        return
    try:
        pynvml.nvmlInit()
    except (OSError, pynvml.NVMLError):
        yield
        return

    stop = Event()
    peak: int | None = None

    def sample():
        nonlocal peak
        while not stop.is_set():
            try:
                used = 0
                found = False
                for index in range(pynvml.nvmlDeviceGetCount()):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(index)
                    total = pynvml.nvmlDeviceGetMemoryInfo(handle).total
                    for process in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
                        if process.pid == pid:
                            # Windows WDDM can return NVML_VALUE_NOT_AVAILABLE.
                            if not isinstance(process.usedGpuMemory, int) or not 0 <= process.usedGpuMemory <= total:
                                on_update('')
                                return
                            used += process.usedGpuMemory
                            found = True
                if found:
                    peak = max(peak or 0, used)
                    on_update(f'VRAM {used / 1024**3:.1f} GiB · peak {peak / 1024**3:.1f} GiB')
                else:
                    on_update('')
            except pynvml.NVMLError:
                on_update('')
                return
            stop.wait(1)

    thread = Thread(target=sample, name='sprute-vram', daemon=True)
    try:
        thread.start()
        yield
    finally:
        stop.set()
        thread.join()
        try:
            pynvml.nvmlShutdown()
        except pynvml.NVMLError:
            pass
        on_update(f'Peak VRAM {peak / 1024**3:.1f} GiB' if peak is not None else '')
