"""Record a command's terminal output as an asciicast v2 file, at a fixed terminal size.

usage: python3 record.py out.cast COLS ROWS -- command ...
"""
import fcntl
import json
import os
import pty
import select
import struct
import sys
import termios
import time

out, cols, rows = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
command = sys.argv[sys.argv.index("--") + 1:]
pid, fd = pty.fork()
if pid == 0:
    os.environ.update(TERM="xterm-256color", COLUMNS=str(cols), LINES=str(rows))
    os.execvp(command[0], command)
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
start = time.monotonic()
with open(out, "w") as cast:
    cast.write(json.dumps({"version": 2, "width": cols, "height": rows, "timestamp": int(time.time()),
                           "env": {"TERM": "xterm-256color"}}) + "\n")
    while True:
        ready, _, _ = select.select([fd], [], [], 1.0)
        if not ready:
            if os.waitpid(pid, os.WNOHANG)[0]:
                break
            continue
        try:
            data = os.read(fd, 65536)
        except OSError:
            break
        if not data:
            break
        cast.write(json.dumps([round(time.monotonic() - start, 6), "o", data.decode("utf-8", "replace")]) + "\n")
        cast.flush()
os.waitpid(pid, 0)
