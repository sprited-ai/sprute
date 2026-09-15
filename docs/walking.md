# Make your character walk

**Development preview — not included in npm 0.4.1 yet.**

Sprute can now take the eight standing poses it generated and make a walking
animation. The first supported motion is walking in place, viewed from eight
directions. Other actions, like jumping and attacking, are not implemented.

First, complete the [one-time setup](walking-setup.md). Then, from that same
Sprute folder, run:

```sh
node dist/cli.js animate outputs/my-character.spritesheet.png --wait
```

Replace `my-character` with your character's filename. Use the eight-view
`.spritesheet.png`, not a single drawing or the `.turntable.webp`. You can make
a standing character with the [character guide](../README.md#make-a-character).
Sprute prepares the
character, requests eight videos, removes their backgrounds, and packs the
frames into one image. If your character has a saved `.sprute.yaml` description,
Sprute uses it automatically. Keep the terminal open while it works.

Open `outputs/my-character.walk/walk/preview.html` when it finishes. The same
folder contains `animation.png` and `animation.json` for your game. Each
direction has 32 frames in 128 × 128 cells by default.

The preview lets you inspect the result. Generation can still change a face,
shoe, or clothing detail. Check the feet and the transition from the last frame
back to the first. Repeating playback is enabled for the walk; this does not
mean the model produced a seamless transition.

Newly generated previews show the original standing pose beside the selected
walking direction. Compare the face, clothes and accessories. The two images
may have different sizes and poses; they are not aligned overlays.

To add that comparison to an older export, create a new preview using the saved
source picture:

```sh
node dist/cli.js preview-animation outputs/my-character.walk/walk \
  --reference outputs/my-character.walk/character.png -o comparison.html
```

The preview includes both images and works offline. Your existing atlas stays
unchanged. Downloaded review notes include the reference image hash when present.

Background removal can lose very thin details or make see-through material
opaque. Check things like antennae, loose hair and translucent clothing against
both a dark and a light background before using the result.

To record a problem, pause on the frame and type a note below the preview.
Typing pauses playback and fixes the note to that direction and frame, even if
you look at another direction before saving. Use **Save note**, then **Download
notes** before closing the page; notes are not saved automatically.

To continue reviewing later, choose **Load review notes** and select the JSON
file you downloaded. Sprute checks that it belongs to the same animation and
original reference when that reference was recorded. Existing notes stay in
place and repeated notes are skipped. Click a note in the list to jump to its
direction and frame. Download the combined notes again before closing.

## Use it in Godot

After checking the preview, run:

```sh
node dist/cli.js export-godot outputs/my-character.walk/walk -o outputs/my-character-godot
```

Copy the resulting folder into your Godot 4 project. Add an `AnimatedSprite2D`
node, then drag `walk.tres` onto its **Sprite Frames** property. Choose a
direction such as `S` and play it. Set **Texture Filter** to **Nearest** for
pixel art. Keep the exported files together, including the `.import` settings.

The eight animation names are `S`, `SE`, `E`, `NE`, `N`, `NW`, `W`, and `SW`.
Your game chooses which one to play when the character changes direction.
Export keeps the frames and their timing; movement controls are up to your game.
Use a new output folder if you export again.

Want to try moving the character first? Add `--demo`:

```sh
node dist/cli.js export-godot outputs/my-character.walk/walk -o outputs/my-character-demo --demo
```

In Godot's project manager, choose **Import** and select the new folder's
`project.godot`. Open it and press **F5**, then use the arrow keys. Hold two
arrows to move diagonally. Releasing the keys pauses the pose; this does not
generate a separate idle animation. The included `player.gd` shows how to
connect input to your eight animation tracks.

## Connect the animation server once

First time here? Follow [Set up walking](walking-setup.md), then come back to
this page. It takes you through building the development version, connecting
the GPU server, and creating the reusable walking guides.

Walking is not available in the published npm 0.4.1 package. The setup still
needs someone comfortable preparing a Linux GPU server. Once connected, you
reuse that setup for your next character.

## Stop and continue

Check progress without starting generation or downloading anything:

```sh
node dist/cli.js animate --status outputs/my-character.walk
```

This works while another terminal is running the animation. It shows which
directions are queued, generating, ready to download, or already downloaded.
Saved job IDs appear beside the directions so you can identify a specific job
when investigating a problem.
If the server cannot be reached, the status is unavailable; that does not mean
the job failed. Status does not take over the running process. Transparent-file
and preview indicators report file presence, not visual approval.

To stop, press **Ctrl+C once** and wait for the resume command before closing
the terminal. Sprute finishes the current processing pass and releases its
lock. If it is submitting jobs or processing videos, this can take a while;
while waiting between server checks, it stops immediately. Submitted GPU jobs
continue on the server. Keep the server running.

Continue using the **same animation folder**, so Sprute can recover those jobs:

```sh
node dist/cli.js animate --resume outputs/my-character.walk --wait
```

Closing the terminal abruptly or force-killing the process can still leave
`.animate.lock`. If that happens, the error identifies the
file. Read its PID and host, confirm that process has stopped, then remove
only that lock file. Keep the `run` folder and its journals.

Completed processing stages are checked and reused. A failed download can be
retried without starting another generation. Once all videos are downloaded,
local processing can finish with the GPU server offline. A failed job or a job
that disappeared from server history needs investigation; Sprute does not
automatically resubmit it.

If Sprute prints “Walking needs attention,” it lists each direction and prints
a ready-to-copy `animate --status` command for that saved folder. Use that command
to check again without starting new jobs. Keep the folder and any displayed job
IDs when asking for help; an unconfirmed job is not proof that generation failed.

Without `--wait`, the command processes available results and exits with code 2
if more directions are pending. Code 0 means export completed; code 1 indicates
an error or a job needing attention. Completion does not mean visual approval.

## Optional settings

You can skip saving project settings by supplying the guides and server directly:

```sh
node dist/cli.js animate outputs/my-character.spritesheet.png \
  --drivers drivers.json --server http://localhost:8188 \
  --description "a girl with brown hair, a blue bow and white sneakers" \
  -o outputs/my-walk --wait
```

`--size 128` sets the square game frame size. `--start 32 --end 63` selects an
inclusive, zero-based range from each generated video. These defaults use the
second 32-frame cycle of the supported 65-frame motion guide. This is a fixed
selection, not automatic detection of the best cycle or matching anatomical
phase across directions. Choose settings when starting; resume keeps them.

Sprute snapshots your source picture and guide manifest. Editing the original
picture later does not alter a saved animation. To try a new character, prompt,
or frame range, use a new output folder.

For troubleshooting, newly processed transparent cycles record the matting model
hash and actual runtime versions. That information follows the frames into the
animation metadata. It helps identify differences between computers or package
versions; it does not guarantee identical pixels across them. Existing outputs
remain usable without these newer fields.

The integrated command currently uses ToonOut background removal. The extra
PyMatting edge refinement in Lily preview 178 remains an experiment and is
not silently included here. The command also retains the current motion-guide
proportions; a chibi-specific guide has not yet been validated.

### Hold drawings for a more stepped rhythm (development checkout)

Keep the walking speed but show fewer drawings:

For a new animation, add the option when starting generation:

```sh
pnpm exec tsx src/cli.ts animate character.spritesheet.png --hold-frames 2 --wait
```

This setting is saved for resume. It changes the exported drawings, not the GPU
generation workload. Existing saved walks keep their original settings.

For transparent cycles you already generated:

```sh
pnpm exec tsx src/cli.ts pack-animation transparent-cycles -o held-walk --size 128 --loop --hold-frames 2
```

Each selected drawing lasts for the summed duration of its source group. Use `3`
for longer holds; a shorter final group retains its remaining time. This also
preserves variable source durations. Registration uses all original frames so
changing the rhythm does not change framing. At least two output drawings are
required. This changes timing style, not anatomy, and does not select contact
poses or validate a seamless loop. For JSON input use the manifest's `holdFrames`
field instead of the CLI flag. This source-checkout feature is not yet published.

## Keep settings in one file

The development CLI also reads walking settings from `sprute.config.json`:

```json
{
  "animation": {
    "server": "http://127.0.0.1:8188",
    "drivers": "motion/drivers.json"
  },
  "preview": { "open": false }
}
```

Use the path to your installed motion-guide manifest for `drivers`; it is relative
 to the project folder. The `animation` section takes precedence over the older
`sprute.animation.json`; command-line `--server` and `--drivers` still override it.
This configures the existing `sprute animate` command. It does not yet make an
image-first standing build start walking automatically. `preview.open` currently
controls the standing preview.
