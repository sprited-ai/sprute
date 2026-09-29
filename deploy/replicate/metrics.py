"""Sample device-wide VRAM and this process tree's RSS, including Comfy children."""
import os
from threading import Event, Thread
from time import perf_counter

import psutil


class PeakMemory:
    def __init__(self, interval=0.2):
        self.interval = interval
        self.stop = Event()
        self.peak_rss = 0
        self.gpu_peaks = {}
        self.error = None
        self.nvml = None
        self.samples = 0
        self.elapsed = 0.0

    def __enter__(self):
        self.started = perf_counter()
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nvml = pynvml
        except Exception as error:
            self.error = str(error)
        self.sample()
        self.thread = Thread(target=self.poll, daemon=True)
        self.thread.start()
        return self

    def sample(self):
        root = psutil.Process(os.getpid())
        rss = 0
        for process in [root, *root.children(recursive=True)]:
            try:
                rss += process.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        self.peak_rss = max(self.peak_rss, rss)
        if self.nvml is not None:
            try:
                for index in range(self.nvml.nvmlDeviceGetCount()):
                    handle = self.nvml.nvmlDeviceGetHandleByIndex(index)
                    uuid = self.nvml.nvmlDeviceGetUUID(handle)
                    if isinstance(uuid, bytes):
                        uuid = uuid.decode()
                    used = self.nvml.nvmlDeviceGetMemoryInfo(handle).used
                    self.gpu_peaks[uuid] = max(self.gpu_peaks.get(uuid, 0), used)
            except Exception as error:
                self.error = str(error)
        self.samples += 1

    def poll(self):
        while not self.stop.wait(self.interval):
            try:
                self.sample()
            except Exception as error:
                self.error = str(error)

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join()
        self.elapsed = perf_counter() - self.started
        if self.nvml is not None:
            self.nvml.nvmlShutdown()

    def result(self):
        return {
            "elapsed_seconds": round(self.elapsed, 3),
            "peak_process_tree_rss_bytes": self.peak_rss,
            "peak_device_memory_bytes": self.gpu_peaks,
            "memory_scope": "GPU: whole device, includes other processes. RAM: summed process-tree RSS, includes shared pages.",
            "sample_interval_seconds": self.interval,
            "samples": self.samples,
            "telemetry_error": self.error,
        }
