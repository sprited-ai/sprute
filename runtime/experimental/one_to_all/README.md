# Experimental One-to-All head conditioning

For a separate checkout of commit `b3c9d886c93c43e767b995e93968708ee2d410cb`,
the following fetches the needed source without example media:

```sh
GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none --no-checkout https://github.com/ssj9596/One-to-All-Animation.git /path/to/runtime/code
git -C /path/to/runtime/code sparse-checkout set video-generation
GIT_LFS_SKIP_SMUDGE=1 git -C /path/to/runtime/code checkout --detach b3c9d886c93c43e767b995e93968708ee2d410cb
```

Then
run `python prepare_code.py /path/to/checkout --check`, then repeat without
`--check` to apply the four inference-only initializer changes. The tool checks
the commit and all target hashes before writing, rejects unexpected edits, and
accepts already prepared files. It does not clone code or install dependencies
or models. Use a dedicated checkout. Neural implementations are not patched.

From the Sprute repository root, model files can be prepared with the shared
verified installer (about 29.8 GB when none are present):

```sh
python runtime/install-models.py /path/to/runtime/models --manifest runtime/experimental/one_to_all/models.json
```

It checks existing files before reuse and refuses mismatches without replacing
them. The manifest pins 17 files to upstream revisions. Weight SHA256 values come
from upstream LFS metadata; small Git files have SHA256 values derived only after
their original Git blob identities were verified. See `sha256Source` per entry.
Experiment 376 verified reuse of all 17 files and fresh download of three small
configuration files. Experiment 377 subsequently installed all 17 files into an
empty directory and passed an independent full-file hash verification.

This is an inference-independent NumPy helper, not the public animation backend
or an installer. It accepts One-to-All's dwpose dictionaries with18 body points
or20 including toes. Existing frame/reference arrays are copied, not mutated.

Use `reference_head(reference, frames)` after official body retargeting to place
reference head/face landmarks relative to the driven neck. This freezes local
head shape/orientation and also replaces head confidence; it is not natural head
motion generation. Then use `drawing_pose(pose, policy=...)` for both reference
and driving inputs, choosing explicitly:

- `reference-head`: retain head markers. The upstream reference renderer still
  omits dense face points; the driving renderer may show them.
- `hidden-head`: remove nose/eyes/ears, incident lines and dense face points from
  both streams. Pass the returned boolean as `without_face` when rendering.

Do not infer visibility from confidence or automatically map every rear diagonal
to hidden-head. Occlusion and nonhuman anatomy remain unresolved. N experiments
292 omit all these markers based on inspected inputs; E289 retains them. Neither
is an accepted general quality solution. Head marker removal loses head position
control, and reference-head loses rotation variation. Body/hands/toes are retained.

The helpers reproduce all69 conditioning files (including encoded video) and
geometry exactly in each of E289 and N292: see experiment293. No diffusion rerun
was needed for this refactor. They require a separately pinned external renderer
and runtime; do not change shared environment dependencies to import this module.

## Known-rig body preparation

`rig_conditioning.py` factors the323 fitting recipe out of experiment scripts:

```python
from rig_conditioning import fit_body, prepare_metadata

body, receipt = fit_body(
    reference_meta['keypoints_body'], rig_body_frames,
    fit_policy='shoulder-width', vertical_lift=0.75,
)
reference, motion = prepare_metadata(reference_meta, body,
                                     head_policy='reference-head')
```

Inputs are normalized20x3 body arrays and Nx20x3 motion. Supply a whole cycle
(default32frames). The projected rig availability values are not confidence in
an image detector. Metadata uses21x3 hands and69x3 face before upstream conversion.
Arrays are copied. No model/Blender/rendering dependencies beyond NumPy are imported.
The body helper does not apply world scaling: choose the3D profile before projection.

Choose `uniform-envelope` explicitly for inspected profiles; do not divide by
near-zero projected shoulder width. `shoulder-width` rejects source widths below
8/512 by default. That bound is experimental and configurable, not a validated
quality score. Visibility is always explicit; no automatic rear/face decision.
`prepare_metadata` omits hands and clears driving head markers. For `reference-head`,
convert metadata to dwpose and apply the existing `reference_head` helper before
drawing; for `hidden-head`, draw without face points. This matches the two evaluated
pipelines, not all possible rig or character anatomies.

Fitting preserves neither3D bone lengths nor physical contact. It scales the
shoulder/ankle envelope and reduces knee/ankle screenY excursions; caller must
review resulting gait. Invalid shapes, nonfinite values, missing anchors and
collapsed envelopes fail before rendering. Coordinates are not silently clipped.

Experiment326 verifies exact body parity for24 view/profile combinations, exact
SE324/NE325 metadata, input-copy behavior and failure cases (7tests). Both resulting
69-file conditioning sets, including encoded pose video, reproduce byte-for-byte.
Run `/tmp/sprute-matting-113-venv/bin/python experiments/326-rig-conditioning-module/verify.py`
in this development checkout, or use Python with NumPy and the saved experiment
fixtures. These checks are not fresh-machine installation or visual-quality proof.
The helper is still experimental and is not wired to the public walking backend.

## World-space arm preparation

`arm_geometry.reduce_abduction(arms, retained_fraction=0.5)` accepts a finite
NumPy-compatible array shaped N×2×3×3: frames, right/left arm, shoulder/elbow/wrist,
XYZ. Coordinates must use Z up. Call this before world scaling and projection.
It returns an independent copy, rotates elbow/wrist rigidly about each shoulder,
and preserves pre-scale arm lengths and elbow flexion. The horizontal shoulder
axis defines lateral direction; world down defines the other rotation axis.

The fraction is explicit: 1 preserves the original coordinates, 0 removes the
upper arm's lateral component. Degenerate shoulders, zero-length segments and
an upper arm with no component in the rotation plane are rejected. This targets
upright humanoid motion; it supplies no collision, IK, foot-contact or unusual-rig
support. Existing anisotropic scaling can still alter effective bone lengths.

Experiment338 verifies five checks including exact reproduction of all eight
336 coordinate sets and W336/SE337 reference/motion metadata, geometric invariants,
translation/yaw equivariance and invalid inputs. The336 preparer now uses this
module and regenerates its coordinate JSON, W metadata and diagnostic overlay
byte-for-byte. No additional diffusion was needed. This remains an experimental
option, not a public backend default or general animation-quality guarantee.

## Prepare metadata from the command line

With Python and NumPy installed, run from the repository root:

```sh
python runtime/experimental/one_to_all/prepare.py \
  --reference reference-meta.json --motion projected-motion.json \
  --output prepared --fit shoulder-width --head reference-head \
  --vertical-lift 0.75
```

`reference-meta.json` is the reviewed detector metadata object with a20×3 body,
21×3 hands and69×3 face. `projected-motion.json` contains `rows`, a list of metadata
objects whose `keypoints_body` arrays are20×3. Apply world-space arm changes and
project the rig before this command. It does not load images, detect anatomy,
render pose maps, download models or generate animation. Keep the corresponding
reference PNG with your source metadata; an input hash alone does not certify
its anatomy or image correspondence.

Fit and head policy are explicit. The output directory must be new and its
parent must exist. The command writes `fitted.json` for the external renderer and
`preparation.json` with source/content hashes and parameters. Invalid metadata
fails before the directory is created; an existing output is never overwritten.
If a disk write fails after creation, inspect the partial output and choose a
new directory for retry. There is no automatic retry or generation job.

Experiment341 checks exact SE324 metadata parity, output preservation, invalid
anchor rejection and a real CLI invocation. This is a developer preparation
command; beginner installation and the public walking workflow remain separate.

## Render the conditioning cache

On the configured experimental runtime (NumPy, Pillow, OpenCV, matplotlib and
FFmpeg), consume the preparation command's fitted metadata:

```sh
python runtime/experimental/one_to_all/render.py \
  --fitted prepared/fitted.json --reference-image reference.png \
  --upstream /path/to/pinned-renderer-files --output rendered
```

The upstream directory must contain the exact pinned `infer_function.py` and
`draw_utils.py`; SHA-256 checks happen before executing the selected drawing
functions. This matches the evaluated One-to-All renderer, not arbitrary code
from a user-selected revision. It requires65 frames and a512×512 reference image.
Head visibility comes from fitted metadata; hidden-head inputs with available
face/head landmarks are rejected. No inference model is loaded.

Output is a new directory containing `cache/` and `conditioning.json`. The cache
contains the reference RGB, black mask, reference pose,65 driving PNGs and24fps
pose video. Source and cache hashes are recorded. Existing output is not replaced;
partial failures remain for inspection. Do not automatically retry into the same
folder. Renderer dependencies are external and are not installed by this command.

Experiment342 reproduced all69 files each for SE337 and hidden-head NW327,
including encoded videos, on the configured server. This establishes parity for
both evaluated head policies; it does not establish fresh installation, anatomy
correctness, completed model integration or animation quality.

## Generate one experimental walk

On the already configured Linux GPU runtime, with its dependency overlay active:

```sh
python runtime/experimental/one_to_all/generate.py \
  --conditioning rendered --runtime /path/to/configured-one-to-all \
  --output generated --seed 42 --prompt ''
```

This consumes `rendered/cache` and its conditioning manifest. It requires the
complete65-frame24fps file set, checks every input hash, rejects escaping file
symlinks and checks the supported inference-source hash before claiming a new
output directory. The configured runtime must already contain its base, VAE and
checkpoint folders; this command does not install or revalidate model weights.
Use the separately verified284 runtime. Do not interpret directory existence as
model-integrity verification or assume other environments are supported.

Sampling remains the evaluated384px65frames30steps, imageCFG2.5/poseCFG1.5 profile.
Seed and caption are explicit CLI options. Seed substitution affects an in-memory
copy of the pinned inference source, saved with the run; shared upstream code is
unchanged. A short-clip adapter supplies a single65-frame chunk.

`state.json` records preflight, loading, generating, completion or caught failure;
`run.json` records inputs/settings; `output-hashes.json` records completed outputs.
The output directory is exclusively claimed and never reused. No automatic
retry/resume is provided. After interruption, inspect the real process as well as
the state file before choosing a new run. Abrupt process death can leave stale
state. Run independent jobs sequentially unless GPU scheduling is managed outside
this command. The public CLI's job service is not connected to this runner yet.

Experiment343 ran against the common renderer's SE output: all65 generated PNGs
match337 byte-for-byte. Repeating the completed output path exits2 and preserves
its state. Four separate preflight checks cover manifest completeness, hash
corruption and escaping symlinks; these do not decode media. Actual inference
checks frame count and dimensions. No fresh installation or new quality claim.

## Run an explicit eight-direction plan

`batch.py --plan plan.json --check` validates every input hash without generation.
The JSON has a `directions` object containing exactly S,SE,E,NE,N,NW,W,SW; each
entry has a `conditioning` path and optional `seed` (42) and `prompt` (empty).
Relative paths resolve against the plan file. Direction names express the caller's
intent: hashes do not verify that an image really faces that direction.

To execute, add `--runtime /configured/runtime --output new-batch` and omit
`--check`. The runner validates all inputs before creating the output, invokes
one generate.py subprocess at a time, and verifies completed frame hashes before
advancing. The batch stores a resolved plan, per-direction logs and atomic state
updates. The first failure stops further dispatch. Inputs are checked again before
each direction so changed files are not silently consumed. Each child also checks
the configured runtime before model loading.

Existing batch output is refused unless `--resume` is explicit. Resume verifies
completed children and refuses partial jobs; see the resume section below.
Automatic retries and GPU resource scheduling are not implemented. After a forced
interruption, inspect live processes before starting another batch; a stale state
file is not proof a child stopped.
Do not start independent batches concurrently on an unmanaged shared GPU.

Experiment344 passes four scheduler-contract tests with a simulated child, plus
real validation of8 configured caches. The synthetic children do not generate
images. An older E manifest was adapted only after real FFprobe65-frame24fps and
hash checks, in a separate copied cache. No eight-direction GPU batch was run
for this validation, and the mixed input set is not quality-approved.

## Review a completed batch

```sh
python runtime/experimental/one_to_all/review.py \
  --batch completed-batch --output rgb-review
```

Requires Pillow and FFmpeg. The command refuses incomplete batches or existing
output directories. It verifies completed frame hashes/dimensions and original
reference hashes, then builds an HTML comparison with8 RGB videos using frames
32–63 at24fps. Original conditioning images must still be available at the saved
plan paths. The page includes coordinated play/pause, restart and speed controls.
It is a review artifact, not a transparent sprite atlas or game-ready export.

Actual batch345 finished all8 jobs and reproduced520 prior PNGs exactly. Review346
built from it and passed a real headless Chrome media/control check. These are
configured-host execution/review results, not fresh installation or visual-quality
acceptance; known source appearance/facing problems remain.

## Export selected RGB cycles for Sprute

```sh
python runtime/experimental/one_to_all/cycles.py \
  --batch completed-batch --output rgb-cycles --start 32 --end 63
```

The inclusive range is explicit. The command requires a complete batch, checks
frame hashes/names/dimensions and copies original PNG bytes into per-direction
`cycle.json` folders understood by Sprute's existing matting/packing code. It
preserves source-frame indices and24fps durations. This selection is not automatic
loop detection or approval. Existing output is refused; partial failures remain
for inspection. The exported pixels still contain their original background.

Experiment347 extracted all256 selected frames from actual batch345. The existing
TypeScript readAnimationCycles function accepted all8 directions, with file hashes,
source indices and timestamps verified. This establishes the format bridge;
ToonOut matting, alpha inspection and atlas/Godot export are subsequent steps.

## Timing measurements

Completed single jobs also write `timings.json`: model loading, each pipeline
call, and total worker time in seconds. CUDA synchronization brackets the loading
and pipeline measurements so these include completion of GPU work. A pipeline
call includes its encoding, denoising and decoding; it is not denoising alone.
Worker time also includes loading inputs and writing images/video. Python imports,
initial preflight, and final output hashing are outside worker time; `state.json`
records the broader job interval.

The current batch runner starts a separate process and reloads the model for each
direction. Timing data can inform a future persistent-worker implementation;
instrumentation alone does not reduce generation time.

An opt-in `batch.py --resident` trial now retains the pipeline across directions.
It preserves per-direction output folders and seeds; `timings.json` records
`modelReused`. Keep the configured runtime and checkpoint files unchanged while
the batch runs. Default subprocess isolation remains available. Actual full-batch
pixel equivalence and timing were checked in experiment 371: all 520 PNGs matched
the isolated batch, with 315.75 seconds versus 498.74 seconds in the earlier run.
This is one configured-host comparison, excluding preparation and matting; the
mode remains opt-in while other inputs and memory limits are evaluated.

`memory.json` records PyTorch CUDA allocated/reserved bytes and their peaks, after
loading and after each pipeline call. Peaks reset before each direction's model
lookup/load, so a reused model's existing allocations are included. Device capacity
and PyTorch/CUDA versions accompany the measurements. These are process allocator
statistics, not total device usage: CUDA context, other libraries and other
processes may use additional memory. They do not establish a minimum GPU capacity
or prove a lower-memory card will run the job.

New `run.json` files record the actual Python executable, search path and loaded
package versions/locations. Historical runs may instead contain a fixed reference
to the experiment 284 dependency overlay; inspect their launch records when
comparing environments. Experiment 375 generated 65 identical PNGs in an isolated
venv without that overlay. Its original Decord wheel failed `pip check` because
upstream renamed the wheel without updating its internal Python tag. Experiments
[379](../../../experiments/379-decord-source-build/README.md) and
[380](../../../experiments/380-rebuilt-decord-inference/README.md) rebuilt the
pinned native source and Python 3.12 wheel: dependency checks pass and all 65
generated PNGs still match. The wheel links system FFmpeg libraries and is not
yet a portable manylinux artifact. The source-build recipe and exact local wheel
hash are retained with those experiments; do not silently retag the old wheel.

## Continue an interrupted batch

The CLI handles Ctrl+C and SIGTERM cooperatively: the current direction finishes,
its output is verified, and the batch pauses before starting another direction.
Keep the terminal open until it reports that it has paused. A second Ctrl+C also
waits; forced process termination can still leave a partial direction. Isolated
child processes run in their own session so terminal Ctrl+C reaches the parent
without interrupting the current child. If the last direction finishes, the batch
reports completion instead of pausing.

For a batch created by the current runner, repeat the same plan, runtime and
output arguments with `--resume` (and `--resident` if desired). Completed
directions are checked against their recorded frame hashes and seed/prompt/input
receipts before they are skipped. Missing directions can then run. Previous
attempt state remains in `previousAttempts`.

An existing partial or failed direction is refused; this command does not erase
it or automatically retry inference. Inspect that job before deciding how to
recover it. Older batches without a saved runtime identity are also refused.
On the Linux/macOS runtime, an OS file lock prevents two batch runners from
advancing the same folder. A leftover `.batch.lock` file is normal; ownership
ends when the process exits. Do not delete it while a runner is active.

CPU lifecycle checks: `python test_batch_resident.py` from this directory.
These cover skipping completed work, refusing corrupted/partial work, live lock
exclusion and failure without retry. Separate CLI processes receive real SIGINT
and SIGTERM during a simulated direction; both finish it, record a paused batch
and exit with 130/143 without starting the next direction. This signal test uses
a simulated generator rather than CUDA. Experiment 373 separately interrupts
after a real GPU child completes but before the parent records completion, then
resumes all remaining directions. The recovered direction's files are unchanged,
and all 520 final PNGs match the original isolated batch. This does not test
an interruption during denoising or a process kill.
