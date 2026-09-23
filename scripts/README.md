# Native Sprute scripts — first CLI implementation

These scripts implement the demo's recipe **without ComfyUI installed or running**.
They do not import Comfy nodes or call its HTTP API. Keep using Comfy for recipe
experiments; these scripts are a separate native execution path.

## Source layout

`scripts/sprute.py` is the CLI entry point. Internal modules live in
`scripts/sprute_lib/`; tests live in the project-level `tests/` directory.
Shared templates and driving videos live in `assets/`. Run tests with
`python -m unittest discover -s tests` from the project root.

Workers run as `python -m sprute_lib.inference` from the scripts directory;
the CLI sets this working directory itself, so callers can launch the CLI
from any directory using an absolute script path.

## Install (uv, Python 3.12; Linux + NVIDIA CUDA for inference)

```bash
cd /path/to/sprute-2
uv venv --python 3.12 .venv
source .venv/bin/activate
# Install the torch/torchvision pair appropriate for your GPU/CUDA first.
uv pip install -r scripts/requirements.txt
python scripts/sprute.py models setup
python scripts/sprute.py models download --stage all
python scripts/sprute.py doctor --stage animate
```

`.python-version` pins the project to Python 3.12. `uv venv` can download that
Python version if it is not installed. The same environment setup works on macOS
for preprocessing, but model inference requires the Linux/CUDA machine.

`models setup` fetches pinned official Python source. `models download` is the
only command that downloads weights; see [model formats](../models/README.md).
FlashAttention is used when installed; otherwise our length-aware PyTorch SDPA
adapter supplies native Wan attention. No separate FlashAttention build is required.
Pillow alone is enough for `--help`, model listing/linking, and `--prepare-only`.

## One command

```bash
python scripts/sprute.py run \
  --prompt "pixel art NPC, a girl with brown hair and a pink dress" \
  --states idle,walk,run --seed 42 --out out/hero

# Start from an existing full-body character instead of generating one:
python scripts/sprute.py run \
  --image examples/elise/reference.png \
  --states idle,walk,run --out out/elise
```

The first implementation uses explicit subcommands rather than the final v2 CLI
grammar. `generate` currently produces the **single reference**, `turntable`
produces the **8-direction standing strip**, and `run` chains the whole recipe.
A freeform portrait is not automatically converted to a correct full-body reference.

## Individual stages

For the linked KJ AniSora FP8 checkpoints, add `--precision fp8` to `turntable`
or `--turntable-precision fp8` to `run`. This uses actual FP8 linear kernels;
BF16 remains the default. The backend probes kernel support before loading models.
On gin, the same 256×256, 81-frame, seed-42 turntable completed in 68s with
17.1 GiB peak PyTorch allocated memory, compared with 86s / 29.6 GiB for the
BF16-expanded checkpoint. This includes loading and ToonOut/export, and is one
run per setting, not a general speed guarantee. It does not change SCAIL2 precision.

```bash
python scripts/sprute.py generate \
  --prompt "pixel art NPC, a knight with a green cape" --out out/hero-reference

python scripts/sprute.py turntable \
  --image out/hero-reference/reference.png --out out/hero-standing

python scripts/sprute.py animate \
  --standing out/hero-standing/standing.png \
  --states idle,walk,run --out out/hero-motion

# Inspect all driver/reference/mask inputs without GPU inference:
python scripts/sprute.py animate \
  --standing assets/sprute-v2-standing-example.png \
  --out out/inspect --prepare-only

# Continue prepared or interrupted jobs with unchanged inputs:
python scripts/sprute.py animate \
  --standing assets/sprute-v2-standing-example.png \
  --out out/inspect --resume
```

`--resume` skips completed stages, not partially completed sampler steps. Changed
settings/inputs require a new output directory. Existing files aren't silently
overwritten. Each inference stage runs in a separate process; GPU memory is
released between stages. `job.json` records settings/input hashes/model paths,
and `performance.json` records process-local PyTorch VRAM peaks and elapsed time.
Those peaks do **not** measure other GPU processes or every driver allocation.

## Recipe and output

1. **FLUX Fill:** SpriteDX 4×2 template, transparent region as fill mask,
   50 steps, guidance 20. Crop cell 6, then ToonOut → `reference.png`.
2. **AniSora V3.2:** 81-frame turntable, 8 steps, CFG 1, shift 5,
   default 256×256. Extract 0/70/60/50/40/30/20/10, crop to 320:512 aspect,
   ToonOut, compose S/SE/E/NE/N/NW/W/SW → `standing.png`.
3. **SCAIL2:** one grid inference for selected states; DPO 1, LightX2V .8,
   8 steps, CFG 1, shift 5. Animation mode by default; `--replace` changes both
   model mode and mask background semantics.
4. **Export:** remove inference padding, split by state and direction, then
   ToonOut on each **cropped character**, and lossy alpha WebP quality 90.

Default driver: 768×768, 24fps, idle 30 + walk 32 + run 20 = 82 frames.
Idle uses the complete 60-frame source cycle sampled every other frame (2× speed).
Inference pads the last frame to 85 (=4n+1), then removes the three padding frames.
The center arrows stay visible in the driving RGB but are excluded from the actor
mask and exports. Metadata, not WebP frame coalescing, defines state boundaries.

```text
out/hero/
  reference/reference.png
  standing/standing.png
  standing/turntable.webp
  motion/prepared/                 # reference, masks, drivers, segments.json
  motion/inference/frames/         # original generated frames
  motion/animations/
    idle/S.webp ... SW.webp
    idle/horizontal.webp
    walk/...
    run/...
    animation.json
```

Each direction also retains PNG frames. Export an existing output again without
rerunning the generators:

```bash
python scripts/sprute.py export \
  --video out/hero/motion/inference/frames \
  --segments out/hero/motion/prepared/segments.json \
  --out out/hero-new-export --quality 80
```

## Validation and known differences

- CPU checks cover direction mapping, state boundaries, temporal padding, mask
  polarity, and SDPA ignoring padded keys. Run `python -m unittest discover -s tests`.
- Native ToonOut and 768×768 SCAIL2 idle/walk/run export completed on gin.
  That animation run took 366 seconds including loading/export, with a sampled
  device peak of 49.0 GiB. These measurements are for the RTX PRO 6000 test host.
- FLUX Fill generation and AniSora 256×256 turntable/export completed separately
  using existing linked weights.
- Both pinned native Wan packages import successfully; the SCAIL attention
  fallback was also exercised on gin's GPU without FlashAttention installed.
- The installed SCAIL2 FP16 checkpoint's **every tensor name and shape** matches
  the official native architecture (checked on a meta-device, without loading 28GB).
- **Full prompt → FLUX → AniSora → SCAIL2 → alpha WebP export passed on gin**
  with seed 42, 256×256 turntable and 768×768 animation. Results are at
  `/mnt/stash/sprute-native-cli/out/elise-full-flow`. Worker times were 41s,
  88s, 339s and 24s respectively (excluding CLI/startup overhead).
  All 24 directional WebPs were checked for RGBA, 256×256 dimensions and
  expected playback duration; PNG sequences contain 30/32/20 frames by state.
  Repeating the same `run --resume` skipped all four completed workers.
  `doctor` itself remains a dependency/path check, not an inference test.
- Native sampling isn't pixel-identical to Comfy: official UniPC schedules and
  AniSora's expert switch differ from Comfy's two KSamplerAdvanced nodes, and the
  linked AniSora FP8 weights are expanded to BF16 for native execution. Seed 42 is not
  a promise of matching pixels. Compare rendered results before relying on parity.
- The turntable prompt preserves the input character instead of hardcoding Lily's
  outfit. Approximate direction selection assumes a successful complete rotation.
- Driver loop boundaries are preserved; diffusion may change timing. No claim
  that generated segment seams are automatically perfect. There is no hidden
  crossfade or automatic deletion of frames.
- CPU preprocessing works on macOS; native inference currently requires CUDA.
  Small-GPU offload tuning and quantized native checkpoints remain future work.

Official implementations: [FLUX Fill](https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev),
[AniSora](https://github.com/bilibili/Index-anisora/tree/main/anisoraV3.2),
[SCAIL2](https://github.com/zai-org/SCAIL-2/tree/wan-scail2),
[ToonOut](https://huggingface.co/joelseytre/toonout).
