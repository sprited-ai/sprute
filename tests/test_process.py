"""Exercise the real deadline against a worker and its child process."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import psutil
from deploy.replicate.process import run_bounded


class DeadlineTests(unittest.TestCase):
    def test_timeout_stops_worker_and_child(self):
        with tempfile.TemporaryDirectory() as directory:
            record = Path(directory) / "child.pid"
            code = (
                "import subprocess, sys, time; from pathlib import Path; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                f"Path({str(record)!r}).write_text(str(p.pid)); time.sleep(60)"
            )
            with self.assertRaises(subprocess.TimeoutExpired):
                run_bounded([sys.executable, "-c", code], timeout=1, cwd=directory)
            pid = int(record.read_text())
            for _ in range(30):
                if not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                    break
                time.sleep(0.1)
            else:
                self.fail(f"Child {pid} survived the deadline")

    def test_worker_failure_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, "code 7"):
            run_bounded([sys.executable, "-c", "raise SystemExit(7)"], timeout=5, cwd=os.getcwd())
