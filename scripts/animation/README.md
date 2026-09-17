# Standalone sprite pipeline scripts

These are **porting seeds for Jin**, not a v2 CLI implementation. Existing `sprute` commands and npm exports are unchanged. Run from any directory using absolute script paths, or use the examples below from the repository root.

Two main entry points:

1. `generate_stills.py`: reference (or text) → template-guided NBP → crop five views → **ToonOut per view** → mirror three views → transparent eight-direction horizontal PNG.
2. `animate.py`: horizontal PNG + `idle|walk|run` driver → Seedance → **crop first, ToonOut second** → loop candidate → transparent horizontal animated WebP.

## Setup

Requires Python 3.10+ on macOS/Linux, FFmpeg + ffprobe, and a running ComfyUI with `ComfyUI-RMBG` / `BiRefNet_toonout` installed. Matting uses that server, not a hosted paid matting endpoint. GPU use and execution time depend on your server. Generated stills use the bundled 8dir-v1 template geometry.

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/animation/requirements.txt
export REPLICATE_API_TOKEN='your-token'
```

Existing environment tokens are used directly; no login. These helpers intentionally do not parse arbitrary `.env` files. Keep your secret out of shell history where possible (e.g. set it through your shell's existing secret-management setup).

The tested idle/walk/run MP4s are included in `drivers/`, with hashes and render provenance. No setup is needed for the bundled presets. To replace them with your own:

```bash
.venv/bin/python scripts/animation/configure_drivers.py \
  --idle /absolute/path/to/idle/driving.mp4 \
  --walk /absolute/path/to/walk/driving.mp4 \
  --run /absolute/path/to/run/driving.mp4
```

This replaces videos in `scripts/animation/drivers/` and updates their SHA256 manifest. The underlying Blender/VRM models and hundreds of intermediate PNG frames are not included. Expected layout is `NW N NE / W empty E / SW S SE`, fixed camera, square grid. The tested source cycle periods are recorded in `presets.json`; they are search hints, not guarantees about generated timing.

The bundled render provenance is in `drivers/manifest.json`. Additional local paths are recorded in `ai/v2-proposals/local-artifacts.json`. `ai/v2-proposals/repro/render-white-drivers.py` preserves the scene/action-transfer experiment. That archived Blender script is environment-specific; rendering new rigs is not part of these two entry points.

## 1. Reference → stills

```bash
.venv/bin/python scripts/animation/generate_stills.py \
  --image ./reference.png \
  --out ./out/hero \
  --comfy http://127.0.0.1:18188 \
  --allow-paid
```

Optional `--prompt 'a girl in a pink dress'`. Omit `--image` for text-only generation; omit both to request an original character. `--template` accepts the bundled v1/v2 layout only. One Nano Banana Pro request, no automatic repairs/retries. No seed reproducibility claim for NBP.

Outputs:

- `standing.png`: alpha PNG, eight equal cells, no extra inter-cell gaps.
- `directions/{S,SE,E,NE,N,NW,W,SW}.png`.
- `reference-grid.png`, `character.json`: composition geometry and provenance.
- `generation/`: request, prediction receipt and raw output.
- `cropped/`, `toonout/`: intermediate inputs, Comfy workflow, outputs.

The template actually generates five views. NW/W/SW are mirrored; text and asymmetric details can flip. Visual review is required before animation.

## 2. Stills → animation

```bash
.venv/bin/python scripts/animation/animate.py \
  --standing ./out/hero/standing.png \
  --preset run \
  --out ./out/hero-run \
  --comfy http://127.0.0.1:18188 \
  --allow-paid
```

Use a **different output folder per preset** (`hero-idle`, `hero-walk`). `--driver /path/to/custom.mp4` overrides the local driver; `--loop full` skips cycle selection. `--seed` defaults42. Seedance defaults480p,1:1,5seconds,no audio. One hosted request per state; no auto retry on failures/moderation rejections. Listing a preset does not guarantee provider acceptance (one prior idle experiment failed).

The animation pipeline calls `postprocess.py` after generation. Its result directory is printed:

```text
hero-run/postprocess/exports/<start>-<end>-q65-optimized/
  horizontal.webp   # same cell dimensions/aspect as standing.png
  horizontal-compact.webp # same cell proportions, height capped at source grid cell size
  grid.webp         # transparent 3x3
  S.webp ... SW.webp
  animations.zip
  export.json       # loop range, timing, transforms, output hashes
```

Exports use lossy WebP Q65, alpha quality80, method6 and size-minimizing frame encoding, source timing and infinite playback. Full-resolution `horizontal.webp` retains the standing dimensions. `horizontal-compact.webp` caps cell height at the source grid cell size (213px for a640px grid) and keeps the cell aspect ratio to pixel rounding. `postprocess/latest.json` points to the latest exports; the command prints loop bounds and file sizes. Change `--quality` without rerunning inference. Source video must have a constant frame rate. Decoder preserves source frame count and rejects VFR instead of silently retiming it.

**Sizing:** default export inverts the reference's square-cell padding. It preserves the standing cell width/height, direction order and zero extra gaps. It does not assert that the model preserved character size. Optional `--register` applies one fixed transform per direction using median height, center and foot baseline against the still; it never rescales each frame. This heuristic must be visually reviewed and stops if it would clip opaque foreground.

**Loops:** both entry points default to auto mode. Standalone postprocessing requires `--preset idle|walk|run` (or infers it from the parent animation job), explicit period bounds, or an explicit `--start/--end`. Use `--loop full` deliberately to keep all frames. Auto mode searches preset period bounds, then selects a five-frame seam window with low image difference. This is a candidate, not certification. Check both the seam and a full left/right gait cycle. Use explicit frame ranges in postprocess for manual correction.

## Reprocess an existing video (no new hosted inference)

```bash
.venv/bin/python scripts/animation/postprocess.py \
  --video ./out/hero-run/prediction/animation.mp4 \
  --standing ./out/hero/standing.png \
  --out ./out/hero-run/postprocess \
  --loop auto --period-min 16 --period-max 23 --quality 65

# Or an explicit inclusive/exclusive range:
.venv/bin/python scripts/animation/postprocess.py \
  --video ./out/hero-run/prediction/animation.mp4 \
  --standing ./out/hero/standing.png \
  --out ./out/hero-run/postprocess \
  --start 23 --end 42 --quality 65
```

Matte inputs/results are hashed and reused. Changing export quality, loop selection or registration does not re-run ToonOut. Changing the source/standing/server requires a new output folder. Export filenames include range/quality/registration. Matte masks and RGB come from original decoded video, not lossy previews.

## Costs and restart behavior

`--allow-paid` authorizes the one new generation call made by that script. Without it, a request plan is saved but submission stops. The flag is not a provider spending cap; use provider billing controls for limits. We do not embed stale price promises. A 5-second480p Seedance video-reference request was estimated around$0.50 in our experiments; still generation and retries are separate.

Rerun the **same command/folder** to resume a known prediction. A marker is saved before POST. If POST's result is uncertain, the script refuses automatic resubmission. Inspect the provider dashboard and recover the original prediction identity; do not delete markers blindly. Failed predictions also stop. No tokens or echoed data-URI inputs are written to manifests. Prediction output URLs can be temporary/private: do not publish run directories wholesale.

ComfyUI has a separate receipt. Cleared server history or uncertain submission requires manual inspection. Local advisory locks prevent concurrent writers to one run folder. Filesystem locks support macOS/Linux; native Windows is not supported by these helpers.

## Validation

```bash
.venv/bin/python -m unittest discover -s scripts/animation -p 'test_*.py' -v
```

Offline tests cover layout round-trip, odd grid boundaries, duplicate-frame timing, loop selection, changed inputs, prediction reuse, and failure/uncertain-submit behavior. Integration smoke checks use existing media and local ComfyUI, not new paid inference. These scripts remain experimental and do not replace visual QA.
