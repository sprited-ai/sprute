# Seedance backend (`--use seedance`)

An optional way to animate a character with ByteDance Seedance 2.0 on Replicate, billed to the user's own Replicate
account. SCAIL2 on the user's GPU stays the default, and nothing in sprute needs Seedance.

## Why

On the hard Quaternius motions with character 0018 (`experiments/seedance-vs-scail2/`, writeup at
blog.sprited.ai/seedance-2-0-8-directional-run), SCAIL2 lightning smears on fast rotation (backflip, roll) and leaves
mannequin parts unpainted (white kicking foot, N-cell legs on death). Full-step SCAIL2 didn't fix either. Seedance
repaints the character every frame and was clean on all of them, and flips heads less often. Both failed the crawl.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Where it plugs in | A `SpruteSeedance` ComfyUI node that replaces SCAIL2's sampler-to-decoder in the existing animate graph; the CLI's `--use` swaps it in | The driver render, background removal, loop cut, every-Nth and the saved-workflow cache all live in the graph. A CLI-side HTTP call between two ComfyUI runs would duplicate or split that. ComfyUI users get the node too. |
| Flag | `sprute animate character --use seedance` (2.0 Fast), `--use seedance-pro` (2.0), default `scail2` | Jin's suggestion. |
| Key | `REPLICATE_API_TOKEN` from the environment, else `.env.local` in the working directory (`*.local` is git-ignored). The CLI loads it into the environment; the node reads it from there | The token is never a node input, so it can't land in the workflow saved inside the WebP. A test checks this. |
| Cost | Printed before submitting, with a `[y/N]` confirm; `--yes` skips it. $0.08/s Fast, $0.10/s Pro with a video input: $0.32 / $0.40 per 4 s animation | |
| Default model | Fast | Seven-motion comparison: no quality difference worth 25% more and ~1.5× the wait. Revisit with the rerun on the fixed driver. |
| Setup | Seedance needs only ComfyUI, sprute's nodes and BiRefNet (`missing_setup(only=BACKGROUND_REMOVAL)`), not the ~20 GB of SCAIL2 weights | A user without a big GPU can still use sprute. |
| Open source | Seedance is opt-in per command, nothing is uploaded without `--use seedance` and a confirm, and the default path stays fully local | Sprute's identity is a local, open pipeline. |

## What changes downstream

Seedance takes whole seconds of driving video and returns 640×640 at 24 fps, 97 frames for 4 s. What assumed SCAIL2's
768 / 81 frames:

- `SpruteRenderDrivingVideo.frames` is 81 in the workflow; the Seedance graph sets 97 (4 s × 24 + 1). The renderer and
  `snap.keep_frames` already work from that number.
- `ImageScale` (592) resizes the decoded grid to the driver grid's size, so 640 → 768 needs no change.
- `ImageFromBatch` (604) keeps `keep_frames`; a loop keeps one cycle from the start, a clip up to its last pose.
- `--scale` / `--draft` scale SCAIL2's inference only; they're rejected with Seedance.
- Motions longer than 4 s are cut at 4 s (the same kind of limit SCAIL2's 81 frames puts on them). Choosing the
  duration from the motion's length (up to 15 s, billed per second) is a follow-up.

## Failure check and retries

Seedance fails in ways that look fine at a glance. The node checks each result against the driver, from the same
gray-background grids, before anything is saved:

- **Didn't move** (crawl: stood idle): mean silhouette IoU between driver and output per direction cell, at 64 px.
  Calibrated on the 26 Seedance runs in `runs-oversized/`: the still crawls scored 0.12–0.14, every followed motion
  0.41 or more (on a driver 17% too tall, so fixed-driver scores should be higher). Fails below 0.3.
  On the fixed-driver rerun (`runs/`, 26 Seedance results) it flags the two crawls (0.12) and one more: death01 on
  Pro (0.14), where the character stands idle for all 4 s while Fast falls correctly. Nobody had noticed that one by
  eye. Everything else scored 0.34–0.57.
- **Grid lines** (Fast crawl): brightness of the cell borders against the cells beside them. +58 on the bad run,
  under +2 on the other 25. Fails above +10.
- **Facing lost** (Fast crawl turned cells to camera): not checked yet. `SpruteCheckDirections` (CLIP-vision facing per
  direction) is on the unmerged `claudia/monster-quadruped` branch; once it's on main, run it on the result.

A failed check raises with the measurements, so a broken animation is never saved. `--retries N` (default 0) tries
again with the next seed; the confirm shows the worst-case cost. Default 0 because every try is billed and some motions
(crawl) fail every time.

## Prompt

From `experiments/seedance-vs-scail2/seedance.py`, ending by whether the motion loops (`loop` in the GLB, which
`motions/quaternius/library.json` also records): "Continue the same motion cycle for the full duration." or "Perform
the motion once as in [Video1], then hold its final pose."

## Risks

- **Loop seams.** SCAIL2 follows the driver's timing exactly, so cutting one cycle wraps. Seedance mostly follows it
  but can drift (sword attack started late on Pro). A loop-seam measure belongs in the check.
- **Safety filter.** White mannequin on #808080 passes; other driver colours were refused. Keep the driver colours
  fixed for this path.
- **Data leaves the machine.** The reference sheet and driver go to Replicate/ByteDance. The confirm says so.

## Slices

1. **Prototype (this PR, draft):** `SpruteSeedance` node, `--use seedance|seedance-pro`, `.env.local`, cost confirm,
   overlap + grid-line check, `--retries`, tests.
2. **Setup without SCAIL2:** `sprute setup --for seedance` that installs only ComfyUI, the nodes and BiRefNet; the
   setup check today also wants every custom node (e.g. ComfyUI-Kimodo) even though animate doesn't use it.
3. **`create character --use seedance`:** pass the backend through `spawn`, with one confirm for all motions' cost.
4. **Cache before confirming:** skip the cost prompt when the saved animation already matches the graph (today the
   cache check runs after the prompt).
5. **Facing check:** bring `SpruteCheckDirections` to main and fail Seedance results whose directions turn to camera.
6. **Loop-seam check:** compare the kept cycle's last frame with its first, against the driver's own seam.
7. **Duration from the motion:** 4–15 s from the snapped motion length, with the cost shown per second.
8. **Recalibrate thresholds** on the fixed-driver rerun (13 motions, `experiments/seedance-vs-scail2/runs/`), and
   decide Fast vs Pro on it.
9. **Docs:** README section on the optional Seedance backend, what's uploaded, what it costs.
