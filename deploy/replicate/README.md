# Sprute on Replicate

This adapter runs Sprute's committed generate, turntable and animate workflows.
Each stage uses the existing headless Comfy runner.

## Standard Cog build

Use Cog's default prebuilt base image. The supported combination is CUDA 12.8,
Python 3.12 and PyTorch 2.8.0 (`r8.im/cog-base:cuda12.8-python3.12-torch2.8.0`).
Keep the default `--use-cog-base-image` setting enabled; no custom Dockerfile,
filesystem repackaging, or base-image override is needed. These shared base
layers are pre-pulled on Replicate, although worker availability and cold-start
latency are still platform-dependent.

```sh
# Generate the schema with the pinned cog==0.16.8 SDK.
python deploy/replicate/generate_schema.py
cog build --openapi-schema openapi-upload.json -t sprute-replicate:test
python -m deploy.replicate.check_image sprute-replicate:test \
  --base-image r8.im/cog-base:cuda12.8-python3.12-torch2.8.0
```

The SDK remains pinned to 0.16.8 for the validated output contract.
`cattrs==23.2.3` preserves compatibility with its `attrs` dependency.
The image check validates runtime versions, schema references and `pip check`.
Actual Cog readiness and inference must also pass before a hosted test.

## Lazy weights

`models/` is excluded from the image. Setup stays lightweight. Each prediction
prepares only the weights needed for its input and requested stages, with a
600-second download deadline. Up to five files download concurrently, largest
first so large animation checkpoints do not start at the end of the deadline.
Inference gets up to 900 seconds within a 1200-second overall request budget;
time spent downloading reduces that budget. Child process groups are terminated
on timeout. Use the smoke test's
`--deadline-minutes 20`; Replicate's setup timeout is independent.

`weights-manifest.json` pins repository revisions, sizes and SHA-256 hashes.
The public Comfy-Org FLUX and VAE copies match the previously bundled files.
Downloaded weights are verified and cached under `/src/models` for the lifetime
of that worker. A new worker has its own cache. No credentials are embedded.
The hosted downloader uses the public Hugging Face endpoint with Xet disabled:
the injected Replicate proxy returned truncated bodies in both Xet-token and
ordinary file requests during hosted testing.
`SPRUTE_LAZY_WEIGHTS=0` disables downloads for offline tests with mounted weights.

Only one prediction runs at a time. Previous outputs are removed when the next
request starts, after Cog has serialized them. The cache is outside that cleanup.
Do not submit another smoke prediction while an earlier one is nonterminal unless
that specific stuck request has been explicitly acknowledged. A failed cancel
call does not confirm that a worker stopped.

The smoke test saves returned files immediately so API output expiry does not
erase test evidence. Use `--input-json inputs.json` for explicit stage or full
pipeline inputs, and run the monitor independently of SSH for long tests.

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

## Local inference

For an offline test, mount a writable model directory and set
`SPRUTE_LAZY_WEIGHTS=0`. RMBG patches its small Python helper in that directory.
For a cold-download test, start with an empty writable directory instead.

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
  --token-file /secure/path/replicate-token --out /tmp/sprute-smoke-unique \
  --deadline-minutes 20
```

This checks visibility and version, submits **one generate-only request**, includes
server-side `Cancel-After: 20m` (10 minutes when the flag is omitted), records its ID/status, and requests cancellation
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
