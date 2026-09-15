# Local character build — development preview

Run from source on the Linux GPU machine containing the configured Python runtime:

```sh
pnpm exec tsx src/cli.ts hero.sprute.json
```

Example character file:

```json
{
  "backend": "local",
  "source": "./hero.png",
  "states": ["standing"],
  "directions": 8,
  "frameSize": 128,
  "output": "./outputs/hero",
  "preview": { "open": true },
  "local": {
    "python": "/path/to/venv/bin/python",
    "runner": "/path/to/sprute/runtime/experimental/qwen/generate.py",
    "comfyRoot": "/path/to/ComfyUI",
    "diffusionModels": "/path/to/verified/qwen/models"
  }
}
```

The runtime uses installed Comfy Python modules; no Comfy server is needed.
Local backend uses no paid API and does not fall back to one. The ToonOut model
may download once into the local cache; subsequent matting runs locally.
Project defaults may be placed in sprute.config.json. Character source and output
paths resolve relative to the character file; project output/runtime paths resolve
from the working directory. Character runtime overrides resolve from its file.

Without arguments the CLI discovers *.sprute.json recursively, skipping hidden,
output, dependency and experiment folders. Use an explicit path inside those folders.
It validates every discovered specification before starting the batch.

Outputs include direction attempt folders (job.json, generation.log and result/), transparent.png per direction,
standing.png, standing.json, build.json and an offline preview.html. Preview opens
with the OS opener where available; on SSH use the printed path and transfer the
output folder to your computer. Generated framing is retained when resizing;
per-direction alignment is not yet normalized.

Current scope: standing only. Idle/walk/run requests fail explicitly before any
model call. A completed build is reused when source bytes, runner bytes, execution settings
and output hashes match. Failed builds resume using verified completed cutouts;
only unfinished directions run again, in new attempt folders. Prior attempts stay
available for diagnosis. Changed inputs require a new output directory for now.
Concurrent builds are excluded by an exclusive lock beside the output folder.
An abruptly killed process can leave a lock and a running journal; automatic
recovery from that case is not implemented. Verify the process has stopped before
handling a stale lock. Ordinary model failures release the lock automatically.
Model weights and installed Python dependencies are not included in this first
cache key: use a new output after changing the runtime or models in place. No npm release contains this path.
The full eight-direction orchestrator completed a real local run in experiment 392
on gin (a physical 96 GB GPU). Native-resolution review in experiment 394 rejected the resulting set:
SE faces left instead of right, duplicating SW. Proportions and fine details also vary.
This proves execution, not final asset quality or physical 32 GB GPU compatibility.
Failure/resume coverage injects a third-direction failure and verifies that the
first two cutouts are reused while the remaining six directions complete.
Direction, identity, proportions and transparency remain quality limitations.

During the Qwen subprocess stage, Ctrl+C/SIGTERM now forwards to that model
process group and waits for shutdown before recording a failed build and releasing
the output lock. Rerunning reuses verified completed directions. A real subprocess
test confirms signal delivery and delayed shutdown, even when the child exits0;
interruption still cannot be reported as a successful generation. GPU cancellation
latency has not been measured. Hard kills, crashes, and interruption during local
matting/packing can still leave a stale lock; those cases are not auto-recovered.
