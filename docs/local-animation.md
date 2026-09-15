# Can I generate animations locally?

Yes, in the development experiments. There is not yet a one-command installer
that takes a new computer from a drawing to a finished walk.

These are separate paths:

| Path | What it does today | Setup |
| --- | --- | --- |
| Published `npx sprute` 0.4.1 | Eight standing views | Replicate account; generation is paid |
| Development `sprute animate` | Standing views → transparent walking atlas and preview | Configured ComfyUI SCAIL-2 server and motion guides |
| Experimental One-to-All runner | Prepared reference and pose caches → eight animated videos | Separately configured Python/CUDA runtime and downloaded models |

The faster One-to-All runner is not yet the backend used by `sprute animate`.
It animates supplied images; it does not replace the standing-image generator.
Our successful local animation trials therefore do not establish a fully local
text-to-character-to-animation workflow.

## What we measured

On gin's NVIDIA RTX PRO 6000 Blackwell, one eight-direction One-to-All batch
took **5 minutes 16 seconds** with `--resident`, which retains the loaded model.
The earlier separate-process batch took **8 minutes 19 seconds**. All 520 PNGs
matched byte for byte, using the same inputs, seeds and prompts. This single
comparison excludes reference preparation, background removal and game export.
See the [batch measurements](../experiments/371-resident-batch/README.md).

A separate 384×384, 65-frame job peaked at **16.88 GiB allocated** and
**17.77 GiB reserved** by PyTorch. Those figures exclude some GPU overhead and
other processes. We have not tested this workflow on a 24GB card, so they are
not a minimum hardware specification. See the
[memory measurements](../experiments/372-gpu-memory/README.md).

## Which instructions should I follow?

To use the integrated development command, start with
[walking setup](walking-setup.md), then [make a walk](walking.md).

To work on the local One-to-All backend, use the
[experimental runtime guide](../runtime/experimental/one_to_all/README.md).
Its `batch.py --resident` option requires already prepared eight-direction
conditioning caches and an installed runtime. It does not download or install them.

The development CLI can now dispatch that runner:

```sh
pnpm exec tsx src/cli.ts animate one-to-all --plan plan.json --python /path/to/venv/bin/python --runner /path/to/batch.py --check
pnpm exec tsx src/cli.ts animate one-to-all --plan plan.json --python /path/to/venv/bin/python --runner /path/to/batch.py --runtime /path/to/runtime -o new-batch --resident
```

Run these on the machine with the prepared caches and GPU runtime. Paths in the
plan refer to that machine. Add `--resume` to the same generation command to
recover completed directions. Ctrl+C is forwarded to the runner's cooperative
pause handler; keep the terminal open until it exits. Output is the raw batch of
videos and frames. Background removal, packing and a game preview are separate
steps for this experimental subcommand. It does not accept a character picture
in place of the prepared plan, and is not in the published npm release.

The setup pieces are becoming reproducible: a separate Python environment and
network-cloned source both load the inference code, and a source-built Decord
package passes dependency checks with identical generated frames. These checks
used the same Linux host. The Decord wheel still depends on that system's FFmpeg
libraries; there is no general cross-platform installer yet. See the
[runtime preparation instructions](../runtime/experimental/one_to_all/README.md)
for pinned code preparation and model installation.

The assembled runtime also completed all eight directions after a fresh model
download, in 319.45 seconds, with all 520 PNGs matching the original run.
[Experiment 381](../experiments/381-assembled-local-runtime/README.md) records the
component and package-path checks. It uses existing prepared conditioning on the
same host; it is not a new-character or new-machine acceptance test.

Neither route guarantees a game-ready walk. Character details, foot contact,
loop transitions and transparent edges still need visual review. The current
work includes successful examples, but generalization to a new character and
fresh-machine setup remain unfinished.

## Turn a completed local batch into a sprite sheet

First review the videos and choose a frame range. The following `32..63` range
is an example from the walking experiment, not automatic loop detection. Both
endpoints are included; 32 frames at 24 fps last 1⅓ seconds.

```sh
pnpm exec tsx src/cli.ts animate one-to-all extract --batch new-batch --python python3 --runner runtime/experimental/one_to_all/cycles.py --start 32 --end 63 -o rgb-cycles
```

Extraction needs Python with Pillow and the adjacent runtime scripts, but no GPU
or model weights. It verifies all eight completed directions and copies the
selected PNGs without changing them. Transfer the complete batch folder if doing
this on another machine. Always choose a new output directory.

Remove backgrounds from each direction with the existing local matting setup:

```sh
pnpm exec tsx src/cli.ts matte-animation rgb-cycles --all-directions -o transparent-cycles
pnpm exec tsx src/cli.ts pack-animation transparent-cycles -o sprite-sheet --size 128 --loop --hold-frames 2
```

Run packing only after matting succeeds. The batch writes `matting-state.json`
with completed directions and any failure. Completed cycles remain available
after a failure; an existing output is never overwritten or automatically retried. `--hold-frames 2`
keeps every second drawing and holds it twice as long, preserving cycle duration.
Omit it to keep every frame. `--loop` enables repeated playback; review the seam
and transparent edges before treating the result as ready for a game.
