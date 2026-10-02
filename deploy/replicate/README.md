# Sprute on Replicate

This adapter runs the committed generate, turntable and animate workflows without
changing their settings. It starts a fresh headless Comfy subprocess per stage.
Each prediction runs in an isolated worker with a 600-second total deadline. On timeout, the worker process group (including Comfy children) is terminated. This bounds inference, not image pull or platform setup time.
Bundled weight reconstruction during setup has a separate 120-second deadline.

Only one prediction runs at a time; outputs from the previous request are removed
when the next request starts, after Cog has serialized them.

## Build and test (Linux with NVIDIA Docker)

Use the Cog 0.23.0 builder with SDK 0.16.8, matching SCAIL-2. Run from the
repository root. The image uses the Python 3.12.14 slim base (not an NVIDIA CUDA
base), CUDA 12.8 wheels, PyTorch 2.11.0 and ComfyUI 0.37.0.1. Custom node commits match
`src/sprute/setup.py`. Transitive dependencies are not fully locked yet.
`cattrs==23.2.3` keeps Comfy's requests-cache compatible with the older `attrs`
required by Cog 0.16.8; the image check includes `pip check` and an import probe.

```sh
# Generate with cog==0.16.8 installed; this imports the predictor without setup.
python deploy/replicate/generate_schema.py
cog build --use-cuda-base-image=false --openapi-schema openapi-upload.json -t sprute-replicate:test
docker pull python:3.12.14-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
python -m deploy.replicate.check_image sprute-replicate:test \
  --base-image python:3.12.14-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
```

The image check rejects damaged OpenAPI references, checks the base layers and
runtime versions against the validated SCAIL-2 stack, and verifies Python permits
Replicate's runtime package installation. It runs without network or GPU access.
Build-time `--break-system-packages` alone does not fix runtime bootstrap: the
container's `EXTERNALLY-MANAGED` marker must also be removed. This check does not
replace starting the actual Cog server and verifying a hosted prediction.

Do not submit another smoke prediction while an earlier one is nonterminal.
A failed cancellation is not confirmation that the remote worker stopped.

For the prepared gin release context containing `models/.parts/manifest.json`,
repackage the validated build before upload:

```sh
python -m deploy.replicate.package_image sprute-replicate:test \
  --tag sprute-replicate:release
```

This pins the base by digest, copies each bundled weight into its own layer,
and excludes the full FLUX checkpoint when its split parts are present. It
preserves Cog labels as Docker CLI arguments so `$ref` strings are not expanded.

## Experimental Kimodo motion

`workflows/sprute-kimodo-motion.api.json` connects Kimodo text-to-motion to the
existing Template-kun renderer. It produces an 81-frame, 24fps transparent
eight-direction driving strip. `generate_motion()` saves that strip;
`animate(..., driving_video=path)` passes it through the existing SCAIL workflow.
The internal `run_pipeline(..., motion_prompt=...)` selects one custom motion
instead of preset motions. It is not exposed as a hosted input until its optional
dependencies and weights are bundled in a release.
Generated clips are finite; seamless looping is not guaranteed.

Kimodo is **not included in the currently published Sprute image**. Its optional
dependency layer can be built on a validated Sprute image:

```sh
docker build -f deploy/replicate/Dockerfile.kimodo \
  --build-arg BASE_IMAGE=sprute-replicate:bootstrap-fixed \
  -t sprute-replicate:kimodo-source .
```

This pins ComfyUI-Kimodo to `9e758bce7f37eb1c4e5d2886463810c98c02b889`, builds
MotionCorrection from source, and corrects the reduced/77-joint skeleton passed
to postprocessing. It installs dependencies only; use the current source checkout
with it. Model weights are separate: the tested offline cache contains
Kimodo-SOMA-RP-v1, Meta-Llama-3-8B-Instruct, and its two LLM2Vec adapters. Mount
that cache at `/src/models/huggingface_cache` and `/root/.cache/huggingface/hub`.
Cold installation/download and redistribution of those additional weights have
not been validated for the hosted image.

The gin integration test generated a right-handed wave and animated the existing
character strip in 167.237 seconds. The 81-frame result preserved eight views in
sampled frames but raised both hands instead of one. This establishes pipeline
connectivity, not faithful reproduction of every generated motion.
The source-built dependency image also completed offline generation; all 81
decoded RGBA frames matched the initial test using the prebuilt native module.

Weights are **not downloaded at startup**. Prepare `models/` before publishing,
using Sprute's pinned model manifest and ordinary Comfy category layout. With the
Sprute dependencies installed in your development environment:

```sh
PYTHONPATH=src python -c 'from sprute.setup import setup_models; setup_models(report=lambda state, message, **kw: print(message))'
```

The download size is reported by setup from the pinned model manifest. HF access to gated repositories must already be
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
state runs independently; `stop_after` and `image_type` allow partial pipelines. Animation uses the current Sprute FP8-scaled SCAIL-2 workflow and renders the bundled GLB motions with Template-kun. `scale` defaults to 1.0 (range 0.5–1.0); smaller values reduce inference resolution while retaining exported sprite dimensions.

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

Base implementation: Sprute commit `627ba7c1121ac2ee8355c844197c20d1eef38119`.
Do not move the existing v0.2.0 tag. A later validated release can be v0.2.1;
Replicate assigns its own version hash. Keep the source commit with deployment
records. Review model hosting licenses (including FLUX Fill) before publishing.

After validation and choosing a Replicate model name:

```sh
cog login
cog push --use-cuda-base-image=false --openapi-schema openapi-upload.json r8.im/OWNER/MODEL
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
server-side `Cancel-After: 10m`, records its ID/status, and requests cancellation
on monitoring failure. It never retries submission, even if the response is lost.
In that case inspect the account prediction list; the server deadline still applies.
Run only one smoke script at a time. This is a request time limit, not a dollar
spending cap or a private-instance shutdown mechanism. Do not automatically retry
failed cold boots. Preserve logs and confirm terminal state before further testing.

## Current Sprute integration check (gin, 2026-09-30)

Source updated to Sprute `627ba7c`, using the existing Cog test environment with
current source mounted. One bounded request ran generate → turntable → walk,
seed 21, animation scale 1.0, with networking disabled and bundled weights:

| Stage | Seconds |
| --- | ---: |
| Generate | 39.501 |
| Turntable | 28.552 |
| Walk (including GLB render and matting) | 203.591 |
| Total | 271.650 |

The returned walk is a 1536×256 RGBA WebP with 81 frames. Frames 0, 40 and 80
were inspected: directions remained recognizable; some shoes are blurred in
motion. This is one integration sample, not a quality/failure-rate benchmark.
Device-wide sampled peak was 75.61 GiB, including other gin workloads; the
Comfy process monitor reported 56.0 GiB. Neither is minimum required memory.
Sixteen adapter/deadline/telemetry tests passed, including a real timeout that
stops a worker and its child. Hosted execution remains to be validated.

The rebuilt `sprute-replicate:current` image
(`sha256:607a7af2369294b980df5de5ce499fde60e244582876c44466dc506a1eea4184`)
is 111.27 GB (Docker's uncompressed size). Its 16 tests and GPU GLB rendering
also passed with networking disabled and no source/model mounts. The full
pipeline measurement above used the earlier environment with current source;
it is not a full inference test of the rebuilt dependency environment.

### Registry upload packaging

The registry rejected the monolithic FLUX Fill layer with HTTP 413. The release
image stores this checkpoint in three parts of at most 8 GiB, in `models/.parts/`.
`manifest.json` records their order, final destination, byte size and SHA-256.
`Predictor.setup()` joins these local parts atomically and verifies the result;
it makes no network request. Other weights retain their normal Comfy layout.
This requires about 24 GB of writable container storage at startup in addition
to the image. The actual in-container assembly and integrity check passed.

The deployment Dockerfile uses one COPY layer per model file/part, preserving
completed uploads. Deployment build records live with the release artifacts.
