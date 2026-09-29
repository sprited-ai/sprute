# Sprute on Replicate

This adapter runs the committed generate, turntable and animate workflows without
changing their settings. It starts a fresh headless Comfy subprocess per stage.
Only one prediction runs at a time; outputs from the previous request are removed
when the next request starts, after Cog has serialized them.

## Build and test (Linux with NVIDIA Docker)

Use Cog 0.23.0. Run from the repository root. The image uses Python 3.12,
CUDA 13.0, PyTorch 2.14.0 and ComfyUI 0.37.0.1. Custom node commits match
`src/sprute/setup.py`. Transitive dependencies are not fully locked yet.

```sh
cog build -t sprute-replicate:test
```

Weights are **not downloaded at startup**. Prepare `models/` before publishing,
using Sprute's pinned model manifest and ordinary Comfy category layout. With the
Sprute dependencies installed in your development environment:

```sh
PYTHONPATH=src python -c 'from sprute.setup import setup_models; setup_models(report=lambda state, message, **kw: print(message))'
```

This downloads roughly 108 GB. HF access to gated repositories must already be
configured. Do not put credentials in the Docker build context. `.dockerignore`
excludes local config and `.env` files; `models/` is intentionally included for
publishing. Use real files: host symlinks pointing outside the build context will
not make their targets available in a deployment.

For gin tests, mount existing weights read-only instead of downloading them again.
Mount any external symlink targets too, or use a directory with regular files.
The pinned RMBG node rewrites `RMBG/BiRefNet/birefnet.py` on load: for real
inference with read-only weights, overlay a writable copy of that file. Baked-in
models use the container writable layer and do not need this extra mount.

```sh
docker run --rm --gpus all \
  -v "$PWD:/src" -w /src \
  -v /path/to/models:/weights:ro \
  -e SPRUTE_MODELS_DIRECTORY=/weights \
  sprute-replicate:test python -m unittest discover -s tests -p test_replicate.py
```

Once weights are in `models/`:

```sh
cog run -i prompt='A cheerful pink-haired adventurer' -i stop_after=generate -i seed=42
cog run -i image=@character.png -i stop_after=turntable -i seed=42
cog run -i image=@character.directions.png -i image_type=directions -i motions=run -i seed=42
# Complete chain, with independent idle, walk and run inference:
cog run -i prompt='A cheerful pink-haired adventurer' -i seed=42
```

The response contains generated images/WebPs plus `metrics.json`. Seed `-1`
chooses a random seed; the actual seed is recorded. The default chains generate, turntable and all three motions. Each animation
state runs independently; `stop_after` and `image_type` allow partial pipelines. No changes to source workflow precision, resolution or LoRAs.

## Memory reporting

Each request prints a `SPRUTE_METRICS` JSON line, including on failure:

- `peak_device_memory_bytes`: NVML device-wide VRAM peak, keyed by GPU UUID.
  Includes other workloads on shared GPUs. It is **not** this prediction's minimum
  required VRAM or PyTorch allocated memory.
- `peak_process_tree_rss_bytes`: peak summed RSS of predictor and descendants,
  including Comfy. Shared pages can be counted multiple times.
- `elapsed_seconds`, sample count, sampling interval (200 ms), telemetry error.

These are sampled peaks; short spikes can be missed. Missing GPU telemetry is an
empty map with an error, never a fabricated zero. Parent-process PyTorch peak
counters would miss the Comfy subprocess, so they are not used.

## Release

Base implementation: main commit `95b7bb43e4719d2b6ac172ec1bb831f9347e8485`.
Do not move the existing v0.2.0 tag. A later validated release can be v0.2.1;
Replicate assigns its own version hash. Keep the source commit with deployment
records. Review model hosting licenses (including FLUX Fill) before publishing.

After validation and choosing a Replicate model name:

```sh
cog login
cog push r8.im/OWNER/MODEL
```

Publishing is a separate step; building/testing this checkout does not publish it.

## Local validation (gin, 2026-09-29)

Cog 0.23.0 container on RTX PRO 6000 Blackwell, existing weights mounted locally,
seed 42. Three successive HTTP predictions passed the actual PNG output of one
stage into the next. Seven adapter/telemetry tests also passed in the container.

| Stage | Seconds | Peak device VRAM (GiB) | Peak summed RSS (GiB) |
| --- | ---: | ---: | ---: |
| Generate | 35.298 | 44.48 | 10.33 |
| Turntable | 27.184 | 36.26 | 5.53 |
| Animate (run) | 196.719 | 95.42 | 17.22 |

GPU figures include other services on gin and Comfy's caching; they do not
establish minimum deployment VRAM. Animation output was an 81-frame 1536×256
WebP. The character, direction strip and three animation samples were inspected;
this is an integration smoke test, not a motion-quality benchmark. Idle/walk,
Replicate-hosted execution, cold-start weights transfer and smaller GPUs remain
untested. These measurements predate the automatic chaining adapter. The updated adapter
passes 8 pipeline/telemetry tests and an offline generate smoke test (43.46s).
The updated single-request generate → turntable → run chain also passed offline:
42.032s / 29.874s / 196.422s (268.331s total). Its 1536×256 RGBA WebP has
81 frames; samples 0, 40 and 80 were inspected. Hands remain close to the torso,
as in the existing workflow; this is not a claim of improved motion quality.
Twelve tests now cover pipeline, telemetry and hosted-smoke safeguards.

## Bounded hosted smoke test

Use the **public model API**, not a dedicated Deployment. Replicate bills private
models and Deployments for setup/idle time; ordinary public model requests do not
have those charges. See https://replicate.com/docs/topics/billing .

```sh
python deploy/replicate/smoke.py --version EXACT_VERSION_HASH \
  --token-file /secure/path/replicate-token --out /tmp/sprute-smoke-unique
```

This checks visibility and version, submits **one generate-only request**, includes
server-side `Cancel-After: 15m`, records its ID/status, and requests cancellation
on monitoring failure. It never retries submission, even if the response is lost.
In that case inspect the account prediction list; the server deadline still applies.
Run only one smoke script at a time. This is a request time limit, not a dollar
spending cap or a private-instance shutdown mechanism. Do not automatically retry
failed cold boots. Preserve logs and confirm terminal state before further testing.
