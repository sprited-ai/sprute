# Eight-direction animation development

For the integrated character-to-walk command, start with [Make your character walk](walking.md).
For the latest verified work and open quality problems, read the
[current walking status](walking-progress.md).
For the distinction between the integrated command and the faster experimental
backend, see [local animation and measured hardware use](local-animation.md).
The individual commands below remain available for debugging and experiments.

The unpublished package has also been installed independently on the same Mac
in [200](../experiments/200-installed-walk-package/README.md). Installed-command
help, real two-frame local matting and offline completed-walk resume work. Current
dependency ranges resolve newer image/ONNX libraries than the development tree;
the sampled RGB pixels match but alpha is not bit-identical. This is not yet a
second-machine or fresh end-to-end generation check.

Sprute's published 0.4.1 release creates standing direction views. Walking
animation generation is still experimental. The rejected WAN results and the
first Seedance candidate are not approved templates.

If you want to make a character today, start with the [three-step guide](../README.md#make-a-character).
The commands below are for developing and testing walking animations from a
source checkout. They require a separately configured ComfyUI server; they are
not yet a beginner-ready walking workflow.

The planner defaults to the fixed **WAN Animate** profile. Choose `--model scail2`
explicitly for the experimental **SCAIL-2** profile described below. Successful
generation does not mean the character or walking motion passed review. See the
[roadmap and acceptance requirements](animation-roadmap.md) before treating an
experimental result as a game-ready animation.

For a short explanation of the current rig-driven SCAIL-2 preview, read
[how the Lily walking example was made](lily-animation-example.md).

## Prepare your standing character for WAN (development checkout)

Start with a transparent PNG strip containing eight equal cells in one row,
ordered S, SE, E, NE, N, NW, W, SW. Sprute's standing spritesheet output uses this
order. The preparation step preserves whatever views you supply; it cannot
recover asymmetric details already mirrored by the standing-view generator.

```sh
node dist/cli.js prepare-animation my-character.spritesheet.png -o my-character-inputs
```

The new folder contains `S.png` through `SW.png` and `character.json`. Each image
is a 512×512 RGB reference on gray (232,232,232), with the nontransparent character
cropped, resized to 360px tall using nearest-neighbor sampling, centered, and
placed at baseline 436. Partial alpha is composited on the gray background.
The manifest records source and output hashes, crops and placements.

Empty cells, completely opaque cells and silhouettes too wide to fit are rejected.
The source is limited to 16,777,216 pixels and 128 MiB. Existing output folders
are never overwritten. Check all eight images before use: transparent noise can
change the crop, and this step cannot detect incorrect facing or extra objects.

This prepares the character references only. It does not upload them, generate
motion, install WAN or create captions. The matching workflow and licensed motion
drivers still need to be prepared separately. These commands are checkout-only;
they are not part of published 0.4.1.

For SCAIL-2 experiments, retain the source-alpha identity maps during preparation:

```sh
node dist/cli.js prepare-animation my-character.spritesheet.png --scail-masks -o my-character-inputs
```

This additionally saves `S-primary.png` through `SW-primary.png`, with their hashes
and encoding recorded as `primaryMask` on each reference in `character.json`.
They use blue for source alpha≥128 and white elsewhere, sampled with exactly the
same crop and placement as the RGB reference. They are SCAIL identity maps, not
transparent output sprites or final background-removal masks. Lily's16 RGB/mask
files match the historical SCAIL inputs byte-for-byte in experiment181.
The option does not change the shared gray-reference profile. The default WAN
planner ignores these extra maps; `--model scail2` validates and copies them.
No generation is submitted by preparation or planning.

## Plan SCAIL-2 workflows (development checkout)

Prepare references with `--scail-masks`, then supply a driver manifest with
`version: 1` and eight `views` entries. Each direction requires `video` (the
server's absolute path to the matching RGB motion video) and `maskVideo` (its
matching SCAIL motion-mask video). These paths must already exist on your server.
The reference identity PNG and the motion-mask video are different inputs.
`upload-animation-drivers` accepts bundles with motion masks as described below.

```sh
node dist/cli.js check-animation-server --model scail2 --server http://127.0.0.1:8188
node dist/cli.js plan-animation my-character-inputs --model scail2 --drivers scail-drivers.json --description "a wingless robot with a red jacket" -o my-scail-plan
node dist/cli.js upload-animation my-scail-plan --server http://127.0.0.1:8188
node dist/cli.js submit-animation-plan my-scail-plan --run my-scail-run --server http://127.0.0.1:8188
```

Planning is offline. It verifies all reference/mask hashes and512px geometry,
rejects identity maps without blue foreground or with unexpected colors, and
writes eight workflows. Uploading verifies all16 local files before network
access and checks all16 remote names before uploading anything. Matching files
are reused; conflicting files stop the command. Only the last command submits
generation. Its persistent run folder provides the same recovery behavior as WAN.

This profile uses `wan2.1_14B_SCAIL_2_fp8_scaled.safetensors`, Wan2.1 VAE,
UMT5 and CLIP Vision H;512px,65frames at24fps, seed7,40steps, CFG3,
UniPC/simple and one reference per direction. It requires `WanSCAILToVideo` and
the matching models/nodes on the server. `check-animation-server --model scail2`
checks this profile's node input names and four model filenames using GET requests.
It does not verify hashes, driver files, GPU memory or successful execution. The
default check remains WAN Animate; choose the same model for checking and planning.

Experiment182 checked the generated graphs against all eight historical Lily
workflows: only input/output names and the generic prompt wrapper differ.
All16 live reference/mask uploads were read back and verified, and a second upload
reused them. Experiment183 completed the planner's unmodified S workflow and
reviewed all65 frames in contact sheets plus five native samples. Frontal identity
persists with redrawn details. Experiment185 also completed the unmodified E
workflow using uploaded motion paths. Native comparisons at indices 8, 24 and 64
look close to the handcrafted-caption baseline, including remaining shoe overlap
and clothing-detail changes. Experiment187 completed N: all65 contacts and native
samples8,24,64 preserve rear facing while exaggerating pale shorts pockets; foot
heights alternate but natural gait is unproven. The remaining five directions,
contact, loops and alpha remain untested through this generic planner.
The motion renderer now prepares SCAIL masks with `--scail-masks`; server setup
still needs separate work;
this is not yet an install-and-generate beginner workflow or a published release.

## Check the ComfyUI server (development checkout)

```sh
node dist/cli.js check-animation-server --server http://127.0.0.1:8188
```

This makes read-only requests for the default WAN profile's 14 node types. Pass
`--model scail2` to check the SCAIL profile instead. It checks
input names (including VHS encoder-specific fields), required inputs and four
model filenames. Missing or incompatible entries are listed in JSON and give a
nonzero exit code. It submits no jobs and installs nothing.

`compatibleNamesAndInputs: true` is a narrow compatibility result. It does not
verify model hashes, licenses, driver files, uploaded references, connection types,
all option values, GPU memory or output quality. Run it before planning/submission,
then separately ensure that the plan's input files exist on the server.

## Plan eight WAN workflows (development checkout)

To build the licensed motion clips locally, use the
[walk-template renderer](../motion/README.md). It accepts the pinned Quaternius
GLB and a new output folder, producing all eight 65-frame videos and paired first
images. A fresh render matched all 256 previously reviewed source PNGs exactly.
Its bundle paths are local. Use `upload-animation-drivers` below to upload the
assets and create the server path mapping.

```sh
node dist/cli.js upload-animation-drivers my-walk-drivers --server http://127.0.0.1:8188 --server-input /path/on/server/ComfyUI/input -o drivers.json
```

Supply the ComfyUI machine's actual input directory, including custom settings.
The API does not verify this absolute directory. All 16 local media files are
hash-checked before network access; first PNGs must be 512px and videos must have
an MP4 container header. This is not video decoding or license validation.
Missing media are uploaded without overwrite and read back with hash verification.
All remote names are inspected for conflicts before any upload. After a lost
response, rerun the same bundle; matching remote files are reused. Partial uploads
can remain after failure, and a server-renamed file stops the operation.
The output JSON is newly created after verification and never overwritten.
Pass it directly to `plan-animation`. No generation jobs are submitted.

For SCAIL, a bundle can additionally contain `D/mask.mkv` in every direction.
Each view in `bundle.json` must then record `maskVideo: "D/mask.mkv"` and
`maskVideoSha256` (replace D with the direction). All eight masks are required
when any mask is present. The upload command checks their hashes and EBML header,
uploads24 files in total, and includes server `maskVideo` paths in its output.
That output can be passed directly to `plan-animation --model scail2`.
The header check does not establish Matroska codec, losslessness, identity colors,
frame timing or correct pairing; those require independent preparation validation.
Experiment184 verified24 live uploads/readbacks, reuse and planner integration.
Create these bundles using the [motion renderer](../motion/README.md) with
`node dist/cli.js render-animation-drivers model.glb --scail-masks -o my-walk-drivers`.
Blender and FFmpeg must be installed, and the model must match the pinned Quaternius
release. Experiment186 checked every decoded mask frame against rendered
source alpha and the earlier masks: all 520 frames matched, along with all 256
RGB source frames. This verifies guide reproduction, not generated gait quality.

After `prepare-animation`, supply the character's appearance and a direction-matched
driver manifest. The planner writes all eight API workflows, so you do not need to
edit ComfyUI node IDs:

```sh
node dist/cli.js plan-animation my-character-inputs --drivers drivers.json --description "a wingless robot with a red jacket and gray shoes" -o my-walk-plan
```

`drivers.json` has `version: 1` and `views` containing exactly S, SE, E, NE, N,
NW, W and SW. Each view has `video`, `firstFrame` and `caption` strings:

```json
{
  "version": 1,
  "views": {
    "S": {
      "video": "/server/motion/S.mp4",
      "firstFrame": "motion/S-first.png",
      "caption": "A blue mannequin walking toward the camera on light gray."
    }
  }
}
```

The snippet shows one entry; all eight are required. Paths refer to the ComfyUI
server. `firstFrame` follows its LoadImage input naming, while `video` follows
VHS_LoadVideoPath. Each first frame and caption must match its motion clip.
The tested profile uses 512px, 24fps, 65 frames, Euler/10, CFG 1 and seed 42.
The bundled graph is Sprute's configuration, with the four model filenames and
node types from experiment 062. Model and motion asset licenses remain separate.

The new folder contains `plan.json`, eight `D.workflow.json` files, and an `input/`
subfolder. Use `upload-animation` below, or copy the contents of `input/` into ComfyUI's
input directory while preserving the generated subfolder name. The planner verifies character image hashes and
geometry, copies their original bytes, and records workflow hashes. It does not
connect to a server or submit jobs. Review the plan before using the existing
`submit-animation` command with a separate journal per workflow.

Server files, installed nodes/models and motion licenses are not validated by this
offline step. The driver setup and submission sequence are still manual. The
appearance wrapper has now generated all eight known Elias views in experiment
068. All 520 decoded frames were inspected in contact sheets. This does not
establish equivalent image quality, unseen-character generalization or usable
foot contact and loop seams.

## Upload the prepared character inputs

```sh
node dist/cli.js upload-animation my-walk-plan --server http://127.0.0.1:8188
```

This replaces copying character inputs over SSH. It verifies all local plan/image
hashes, the workflow reference paths and 512px geometry before network access.
It checks all eight remote names first, reuses byte-identical files, and uploads
missing PNGs with overwrite disabled. Each upload is read back and hash-checked.
It never submits a workflow or uploads motion drivers.

If a response is lost, rerun the same plan: the command checks existing remote
files before uploading. A conflicting file stops the operation. Already uploaded
inputs remain available after failure. If a concurrent upload causes the server
to return a renamed path, the command stops rather than changing your workflows;
inspect that server file. This is recovery through remote file inspection, not
an atomic eight-file transaction. The JSON result lists uploaded/reused views.

## Submit or resume all eight directions

After server checking, input upload and driver setup:

```sh
node dist/cli.js submit-animation-plan my-walk-plan --run my-walk-run --server http://127.0.0.1:8188
```

This submits the eight saved workflows and can use substantial GPU time. It does
not install models, upload inputs, or verify driver paths. The new run folder
contains hashed workflow snapshots, a server binding, an attempt record and a job
journal per direction. Keep this folder. It can contain character descriptions
and server paths; do not publish it without reviewing its contents.

Rerun with the same run folder after interruption. Existing job journals are
recovery-only; directions never attempted can continue. Unknown or failed jobs
stop further submissions. An attempt record without a journal is ambiguous and
stops the command rather than being retried. Inspect the server/run manually in
that case. Never delete attempt records or use a fresh run folder to recover:
that discards duplicate protection. Concurrent invocations may report an in-flight
attempt as unknown; recheck the same run later.

Recovery uses the run's saved workflows even if the original plan folder is gone.
Changing the server or a saved workflow is rejected. Submission still requires a
ComfyUI server honoring client-supplied prompt IDs. The command returns per-view
job IDs/states; use `collect-animation` to download completed videos. It does not
wait for generation, select loops or certify output quality.

## Collect the batch videos

```sh
node dist/cli.js collect-animation-run my-walk-run
```

This reads the run's saved server and direction job IDs. Completed videos are
saved under `my-walk-run/results/S/` through `SW/`; pending states are reported.
Run it again as generation finishes. It never submits or restarts jobs. It exits
2 while results are incomplete, 1 for a reported failed job or an error, and 0
when all eight videos are present. Missing journals are reported as unattempted
or unknown depending on whether an attempt record exists.

Downloaded files carry a SHA256 hash. Reuse verifies job identity, byte count and
hash without needing server history; a changed file is rejected rather than
silently trusted or overwritten. The one-video collector now also saves this
hash. Hashless older downloads are not accepted for batch reuse. This is file
integrity, not video-content or motion-quality validation. Review each saved
video with `review-animation`; collection does not select or approve loops.

## Remove a selected cycle's background locally

After `extract-cycle`, run:

```sh
node dist/cli.js matte-animation selected-cycle -o transparent-cycle
```

This uses the existing local ToonOut model, processing one frame at a time. The
first use may download the cached model and requires the optional
`onnxruntime-node` dependency. It does not submit to a paid image provider. Supply
the original RGB frames where possible; pre-keying away pale character details
cannot be undone by matting.

The input is a single-view `cycle.json` folder from `extract-cycle`; grid cycles
must be separated first. The new folder contains RGBA PNGs and `cycle.json`, with
frame order, source indices and durations preserved, plus hashes of source and
output PNGs. Packing checks the output hashes, so changing a matted PNG afterwards
requires creating and reviewing a new cycle. Older matted folders without output
hashes remain readable but cannot establish that their pixels are unchanged.
It never overwrites the source or an existing destination. Invalid inputs fail
before inference; inference failures remove temporary outputs. Rerun with the
same absent destination after fixing a failure. Interrupted processing is not
yet resumable frame by frame.

Inspect the new frames on light and dark backgrounds. Independent-frame matting
can flicker, leave fringes, or remove thin/translucent details. A controlled test in
`experiments/112-thin-translucent-oracle` also makes a 35%-opaque scarf almost
fully opaque and fills blank space around thin antenna lines. RGB edge correction
does not repair those alpha errors. Output remains
unreviewed; a transparent file does not establish a usable loop. Use the new frame
paths in a `views` packing manifest after reviewing all eight directions.

### Pack cycle folders without listing every PNG

If your parent folder contains `S`, `SE`, `E`, `NE`, `N`, `NW`, `W`, and `SW`
cycle folders, you can pack them directly—no JSON file to write:

```sh
node dist/cli.js pack-animation my-cycles --size 128 --loop -o my-walk
node dist/cli.js preview-animation my-walk -o my-walk.html
```

Each direction folder must contain `cycle.json` and its recorded `frames/` PNGs
from extraction or matting. The command follows those recorded frame lists and
durations, checks available PNG hashes, and rejects missing directions or mismatched
timelines. It does not sort filenames or guess a walking phase.

`--size 128` makes square 128px cells. One fixed transform per direction places
the median silhouette at90px tall, baseline109, centered at64; resampling uses
nearest neighbor and preserves sampled RGBA. For other sizes (4–2048), height is
rounded from70% and baseline from85% of the cell. Clipping is rejected. Without
`--size`, the original dimensions and RGBA are retained, subject to atlas limits.
`--loop` requests repeated playback; without it, playback stops at the end.
Frame durations remain exact; the metadata fps is their nominal average. These
options are for folder input only. This is an unpublished development command,
and it does not generate animation or approve the result.

For custom folder names or registration settings, save a `walk.json` beside
your direction folders. Each path names a folder containing `cycle.json`:

```json
{
  "version": 1,
  "cellWidth": 128,
  "cellHeight": 128,
  "fps": 24,
  "loop": true,
  "cycles": {
    "S": "S/matted", "SE": "SE/matted", "E": "E/matted", "NE": "NE/matted",
    "N": "N/matted", "NW": "NW/matted", "W": "W/matted", "SW": "SW/matted"
  },
  "registration": {
    "sourceWidth": 512, "sourceHeight": 512,
    "targetHeight": 90, "baseline": 109, "centerX": 64, "alphaThreshold": 128
  }
}
```

```sh
node dist/cli.js pack-animation walk.json -o my-walk
node dist/cli.js export-godot my-walk -o godot-walk
```

The example frames 512px transparent inputs on 128px cells. Omit `registration`
and set cell dimensions to the source dimensions to copy pixels without resizing,
within atlas size limits. Frame order and original source indices come from each
cycle, so no PNG list is needed. Explicit cycle durations, including variable
durations, are retained; `fps` supplies the export's nominal rate. All views need
the same frame count and matching timelines (10-microsecond tolerance).
Different source indices are allowed: selecting the correct gait phase is still
your responsibility. Do not combine `cycles` with `views`, `frames`, `columns`
or `directions`. Packing and requesting repeated playback do not approve the loop.

When a cycle frame records a SHA256 hash, packing checks the exact PNG bytes it
decodes against that hash and stops before creating output if they differ. This
also applies when resizing through registration. Older cycle files without
hashes remain supported, but cannot establish that the images are unchanged
since extraction or review. Restore the intended frames or create and review a
new cycle after edits; do not remove hashes merely to bypass a mismatch.

## Submit a prepared local workflow (development checkout)

The experimental command accepts ComfyUI's **API-format** workflow JSON. It does
not yet prepare character inputs, install models, or generate eight views for you.
Referenced files must already exist on the ComfyUI server. The workflow determines
which nodes execute, including any paid provider nodes; inspect it before use.

```sh
node dist/cli.js submit-animation workflow-api.json --journal walk-job.json --server http://127.0.0.1:8188
```

Requires a ComfyUI server that honors client-supplied `prompt_id` UUIDs, as verified
on our gin installation. Older servers that assign their own IDs are unsupported:
if a response is lost, the locally saved ID cannot recover such a job.

Sprute exclusively creates the journal and flushes its ID to disk **before**
submitting. Keep that file. Running the same command with the existing journal
only checks the saved job, even when its history is absent or the original workflow
has been removed. There are no automatic submission retries. The journal stores
the server URL, timestamp, ID and workflow hash, not prompts or credentials.

After a timeout, run the same command again. An `unknown` result can mean cleared
history, a changing queue, or a request that never reached the server; it does not
prove failure. Do not delete the journal to retry. Inspect ComfyUI before explicitly
choosing to create a separate job with a new journal. HTTP rejection also leaves
the journal intact. Client IDs are recovery handles, not server-side deduplication.

Use the printed `collect-animation` command to download a completed video, then
`review-animation` to inspect every frame. Tested submission/recovery does not
certify animation quality or make this a beginner-ready generation workflow.

## Pack existing frames (development checkout)

This is the first shared export path for animation providers. It does not call
an AI service, remove a background, generate motion, or assess animation quality.

Build this checkout with `pnpm build`, then describe your PNG frames in JSON:

```json
{
  "version": 1,
  "cellWidth": 64,
  "cellHeight": 96,
  "columns": 4,
  "directions": ["S", "SE", "E", "NE", "N", "NW", "W", "SW"],
  "fps": 8,
  "loop": false,
  "frames": ["frames/step-00.png", "frames/step-01.png"]
}
```

Each input image contains eight views of the same moment. This example expects
256×192 images: four columns, two rows, no padding. Directions describe source
cells in reading order. All eight directions are required, without duplicates;
1, 2, 4, or 8 columns are supported. Supply all the frames you want to play in the
exact order. Paths resolve relative to the JSON file, not the terminal directory.

```sh
node dist/cli.js pack-animation walk.json --output my-walk
```

The new folder contains:

- `animation.png`: one row per direction, one column per moment. Output rows
  always follow S, SE, E, NE, N, NW, W, SW, even if the input order differs.
- `animation.json`: image filename, frame rectangles, FPS, durations in
  milliseconds, playback preference, and source frame order. Use the same frame
  index when changing direction in your game.

Pixels, including partial alpha, are copied without resizing or compositing.
Opaque inputs remain opaque. This command never invents missing views by mirroring.
`loop` defaults to false; setting it to true requests repeated playback but does
not repair or certify the seam. Review status is always `unreviewed`.

The output directory must not exist. Source geometry is checked before output
creation. Atlas dimensions are limited to 16,384 per axis and 16,777,216 total
pixels; reduce frame count or resolution for larger clips. The implementation
currently decodes the selected source frames into memory, so small game-size
inputs are preferable.

The browser-safe `packAnimation` function is exported from the core library for
providers and future app integrations. It accepts RGBA images and the same layout
fields, and returns a raw atlas plus metadata.

### Pack separate direction frames

If each direction already has its own PNG sequence, use `views` instead of making
eight-cell grids. The same `pack-animation` command accepts this manifest:

```json
{
  "version": 1,
  "cellWidth": 128,
  "cellHeight": 128,
  "fps": 24,
  "loop": true,
  "views": {
    "S": ["S/01.png", "S/02.png"],
    "SE": ["SE/01.png", "SE/02.png"],
    "E": ["E/01.png", "E/02.png"],
    "NE": ["NE/01.png", "NE/02.png"],
    "N": ["N/01.png", "N/02.png"],
    "NW": ["NW/01.png", "NW/02.png"],
    "W": ["W/01.png", "W/02.png"],
    "SW": ["SW/01.png", "SW/02.png"]
  }
}
```

All eight directions must have the same number of frames, at least two. Every
PNG must match the declared cell dimensions. Paths resolve relative to the
manifest, and array order is playback order. Do not include `frames`, `columns`
or `directions` with `views`. The output uses the same atlas and timing format
as grid input, preserving decoded RGBA pixels exactly. It neither aligns gait
phases nor resizes, mirrors, removes backgrounds or fills missing directions.
For unequal source frame rates, explicitly prepare a shared timeline first.

### Optional fixed framing for separate views

For transparent character sequences with mismatched scale or position, add a
`registration` object to a `views` manifest. `cellWidth` and `cellHeight` describe
the output canvas; `sourceWidth` and `sourceHeight` describe each input PNG:

```json
"registration": {
  "sourceWidth": 512,
  "sourceHeight": 512,
  "targetHeight": 90,
  "baseline": 109,
  "centerX": 64,
  "alphaThreshold": 128
}
```

This example fits a 128×128 output canvas. Sprute measures the cycle-median
silhouette height, horizontal center and bottom at the chosen alpha threshold,
then applies one isotropic scale and translation to every frame in that direction.
It preserves frame order and within-cycle movement; it does not independently
center every frame. Silhouettes include hair, equipment and clothing, so matching
bounds does not prove matching anatomy or planted feet. Inputs must already have
useful alpha: this operation does not remove backgrounds.

Nearest-neighbor sampling uses an explicit inverse pixel-center mapping and copies
the selected pixel's RGBA values. Resampling changes the source pixel grid; it may
remove thin details and can differ from other libraries at sampling boundaries.
The CLI rejects empty silhouettes and transforms that would move any nontransparent
source pixel outside the canvas, including pixels below the measurement threshold.
Use a smaller target height or more canvas space if that happens. The source pixel
budget is 16,777,216 per direction; output atlas limits still apply.

All eight transforms and input options are saved in `animation.json.registration`.
Omit `registration` to retain exact-pixel packing. Grid input does not accept this
option. The browser-safe `registerAnimationView` core function exposes the same
operation for a single direction's sequence.

## Evidence so far

- Experiment 010: incorrect WAN model/node pairing initially produced little
  stepping. Correcting it produced motion, but the generated gait was rejected
  for anatomy and exaggerated strides. Increasing driver amplitude was not a
  valid quality fix. Whole-grid matting also damaged pale wings.
- Experiment 011: Seedance 1.5 Pro gave a less extreme side-view candidate, but
  facing and wing shape drifted. No approved loop or WAN transfer yet.
- Export implementation: byte-level tests cover every direction, time, and RGBA
  channel. File integration tests cover explicit frame order, metadata, invalid
  source files, and refusing to overwrite existing output. A built-CLI smoke test
  packed 12 full-grid frames from experiment 010 into 96 atlas cells. That checks
  file processing only; the source art remains rejected.

See [the year-long development plan](animation-roadmap.md) for remaining work.

### Seedance → WAN follow-up

A second Seedance test with identical first/last reference images improved facing
in sampled frames, but returns to standing and still changes details. That RGB
clip was transferred with `WanAnimate2ToVideo` and the matching distilled WAN
Animate 2 model: 65 frames at 512×512, about 80 seconds locally. Sixteen sampled
native frames show small steps without the extreme splits of experiment 010.
This is one-direction transfer evidence, not proof of a good looping template or
an eight-direction generator. The side-by-side viewing copy and exact workflow
are in `experiments/011-seedance-walk-template/wan-transfer/`.

## Review every video frame locally

Install FFmpeg so `ffmpeg` and `ffprobe` are on PATH, then build this checkout:

```sh
pnpm build
node dist/cli.js review-animation walk.mp4 -o walk-review
```

Open `walk-review/index.html` in a browser. Use **Last** to inspect the ending,
arrow buttons to step through exact decoded frames, and **Play** to repeat the
whole clip. For a video containing eight cells in four columns and two rows:

```sh
node dist/cli.js review-animation grid.mp4 -o grid-review --grid 4x2
```

The View menu enlarges one cell; cell numbers follow reading order and do not
infer direction labels. Return to Whole frame to inspect extra objects outside
a selected cell. Notes are attached to zero-based frame numbers; download them
before closing or refreshing the page. They do not automatically mark an asset
approved, and this command does not generate or fix animation.

All decoded frames, including the last one, are retained as PNGs. `review.json`
records source-relative timestamps, the grid, the source video's SHA256 and each
PNG's SHA256. Downloaded notes include the source hash and selected frame hashes.
The source is checked again after decoding; changed content aborts review creation.
Older review folders lack these hashes. Hashes identify files, not animation quality,
and playback does not automatically verify files edited after creation.
Playback follows those frame
durations but can run slowly while large images load; use frame stepping for
precise comparisons. Audio is omitted. No API key or network service is needed.
Output folders must be new. Limits are 600 frames and 128 million decoded pixels
per review; trim/resize larger clips first. Normalize rotated video metadata
before import. The FFmpeg integration test also requires FFmpeg on PATH.

This command is available in the development checkout and has not been published
to npm. Viewing a clip is not evidence that it is usable: inspect facing,
anatomy, contact, identity, late extra objects and loop continuity separately.

## Recover an existing ComfyUI animation

After submitting a workflow in ComfyUI, keep its prompt/job ID. The development
CLI can retrieve its saved MP4 or WebM without submitting another generation:

```sh
node dist/cli.js collect-animation --job YOUR_JOB_ID -o recovered-walk
node dist/cli.js review-animation recovered-walk/animation.mp4 -o recovered-review
```

The default server is `http://127.0.0.1:8188`. Use `--server URL` for another
reachable ComfyUI API, and `--node 15` to select an output node when several nodes
saved videos. If one selected node has multiple videos, this version refuses the
ambiguous selection. It supports saved output videos, not temporary previews.
It does not authenticate to a protected web UI; use an existing trusted local
connection or SSH tunnel. Do not expose a ComfyUI server publicly for this command.

The command checks once. `running`, `queued` and `unknown` return exit code 2;
a recorded failure returns 1. Retry the same job ID later. An unknown ID can mean
history was cleared or changed between reads; it does not prove the job failed.
Network errors and failed downloads never trigger a new submission. No POST
requests are made by this command.

Completed downloads go into a new folder with `animation.mp4` (or `.webm`) and
`job.json`. Existing folders are not overwritten, partial downloads are removed,
and downloads are limited to 512 MiB. The metadata contains the job ID, output
node and byte count, but excludes raw workflow history, credentials and remote
filesystem paths. Review status starts as `unreviewed`: recovering bytes neither
approves a video nor preserves a separate previous review decision. Run visual
review before using it. This is recovery support, not yet a Sprute generation
provider or an automatic retry/submission system.

### Record foot landmarks for comparison

The review page has an optional **Mark foot positions** section. Pause the video,
choose the character's left/right ankle or toe tip, and click the visible point.
For grid videos, select a single cell first. Certainty defaults to **Uncertain**;
choose **Clear** only when both the point and its anatomical identity are visible.
Use **Not visible** for covered or occluded points; no coordinate is invented.
**Clear this mark** removes only that point in the current frame and cell.

Downloaded review notes include each mark's original decoded frame index, file,
time, zero-based cell, anatomical label, visibility, certainty, and full-image
pixel coordinates. Coordinates account for display scaling and selected-cell
offsets. Marks are reviewer observations, not automatic joint tracking or foot
contact evidence. They do not shift frames or approve a loop. Download notes
before closing; marks are not saved automatically or imported on reopening.

The emitted page script is tested for scaled grid coordinates, missing-point
records and frame-specific clearing. Native browser interaction remains pending
because the test Mac was locked. Use cautious review until that check is complete.

### Choose a repeat range

In a newly generated review page, move to a frame and click **Set loop start
here**, then move later and click **Set loop end here**. The end frame is
included. **Play** repeats only that range; starting playback outside it jumps
to its beginning. At least two frames are required when setting boundaries.
**Loop start/end** jump to the join for comparison. **First**, **Last** and the
slider still access the entire original clip; **Use whole clip** resets the
selection. No source frames are deleted or synthesized.

Downloaded review notes now include `selectedRange`, its original frame indices,
frame file references, timestamps and summed duration. Selection remains
`unreviewed`: a repeated range is not automatically a seamless cycle, nor is its
left/right foot phase automatically aligned to other directions. Download before
closing the page; selection and notes are not persisted automatically. This does
not yet export a trimmed video or eight-direction atlas.
## Export a selected cycle

After reviewing every frame and selecting an inclusive range, use the development
CLI to copy that range:

```sh
node dist/cli.js extract-cycle path/to/review --start 27 --end 39 -o new-cycle
```

Extraction checks each selected PNG against its review hash when present and
verifies the staged copy before saving the output folder. `cycle.json` retains
the review-file hash, recorded source-video hash, and each extracted PNG hash.
Older reviews without hashes remain supported: their current PNGs are hashed at
extraction, but this cannot certify what those files contained at review time.
The source-video hash is retained metadata; extraction does not reopen the video.

Frame numbers are zero-based and both endpoints are included. The command writes
the original PNG bytes into `new-cycle/frames` and saves `cycle.json` with source
indices, frame durations and a timeline starting at zero. It preserves variable
frame durations, alpha and any full-frame grid; it does not crop cells, interpolate,
blend, remove backgrounds, or certify the loop. Output directories must be new.
No FFmpeg or model key is needed for this step after a review has been extracted.
The exported status remains `unreviewed`; inspect the join before using it in a
game. This command is not yet in the published npm release.

## Preview a packed animation (development checkout)

After `pack-animation`, create a portable browser preview:

```sh
node dist/cli.js preview-animation my-walk -o walk-preview.html
```

Open the HTML file in a browser. It embeds the original atlas and needs no server,
API key or internet connection. Select directions, play slowly, step frames, and
switch between dark, white and green backgrounds. Direction changes preserve
playback time. Recorded frame durations and the packed loop setting are honored;
non-looping tracks stop on their last frame. Notes can be downloaded as JSON bound
to the atlas and metadata hashes. Download notes before closing the page.

The command validates all eight tracks, rectangles and PNG dimensions and refuses
to overwrite an existing file. It does not approve foot contact, matching gait
phases, transparent edges or a seamless loop. This command is not yet published
to npm.

## Export for Godot (development checkout)

After packing your animation, run:

```sh
node dist/cli.js export-godot my-walk -o godot-walk
```

1. Copy the entire `godot-walk` folder into your Godot 4 project.
2. Add an `AnimatedSprite2D` node.
3. Drag `walk.tres` onto its **Sprite Frames** property.
4. Choose a direction animation and play it. Use **Texture Filter → Nearest**
   for pixel art.

Keep the PNG and its `.import` settings alongside `walk.tres`. The settings
preserve source colors by disabling Godot's automatic alpha-border correction;
lossless import and no mipmaps are explicit. The output preserves all eight
tracks, frame order, explicit durations and loop preference. It never overwrites
an existing destination. No model key or installed Godot is needed to export.

The generated resource was imported in Godot 4.7.2 and all 256 Elias frame crops
matched the source RGBA exactly. A separate three-frame fixture also passed
100/250/150 ms duration checks and stopped on the last frame in all eight
non-looping tracks. This verifies export compatibility, not anatomy,
foot contact or seamless loops. This command is not in published version 0.4.1.

## Try the exported animation in Godot

[Experiment 060](../experiments/060-godot-import/README.md) contains a runnable
Godot project loading the actual Elias atlas and metadata. Godot 4.7.2 passed
256 decoded RGBA crop comparisons, duration checks, frame/progress-preserving
direction switches, playback and a loop signal. A real GPU-rendered screenshot
was also inspected. This is an experimental example with a fixed validation
fixture; it does not establish animation quality or a supported generic importer.
