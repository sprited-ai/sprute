# Sprute on Replicate

This adapter runs the committed generate, turntable and animate workflows without
changing their settings. It starts a fresh headless Comfy subprocess per prediction.
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
cog run -i operation=generate -i prompt='A cheerful pink-haired adventurer' -i seed=42
cog run -i operation=turntable -i image=@character.png -i seed=42
cog run -i operation=animate -i image=@character.directions.png -i motion=run -i seed=42
```

The response contains generated images/WebPs plus `metrics.json`. Seed `-1`
chooses a random seed; the actual seed is recorded. Animate accepts idle/walk/run,
one state per call. No changes to source workflow precision, resolution or LoRAs.

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
