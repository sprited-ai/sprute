# Sprute 2.0 File Structure

Status: proposal. This document describes the intended source layout and generated character format for Sprute 2.0, not an implemented CLI contract.

The [README](../README.md) describes generating character stills, then animating them with named presets. The [task list](../TASKS.md) also calls for horizontal
strips, loop trimming, and padding. The structure below gives those steps a shared
file format while keeping model-specific working files separate from usable assets.

## Repository layout

The current repository contains documentation, example assets, empty `cli/src/`
and `scripts/` directories, and the previous implementation under `outdated/`.
There is no active root package manifest yet. The proposed layout is:

```text
sprute/
├── cli/
│   ├── package.json           # Publishable sprute package and bin entry
│   ├── tsconfig.json
│   ├── src/
│   │   ├── index.ts           # Argument parsing and command dispatch
│   │   ├── commands/
│   │   │   ├── generate-character.ts
│   │   │   └── animate-character.ts
│   │   ├── pipelines/         # Generation and animation orchestration
│   │   ├── providers/         # Model service calls, polling, and downloads
│   │   ├── media/             # Extraction, matting, padding, and strip assembly
│   │   └── character/         # Manifest types, validation, and file I/O
│   ├── templates/             # Bundled image and motion guidance assets
│   └── dist/                  # Generated build output; ignored by Git
├── scripts/                   # Development experiments and maintenance helpers
├── docs/
│   ├── 001-file-structure.md
│   └── resources/             # Images used by documentation
├── examples/                  # Curated inputs and sample outputs
├── outdated/                  # Historical implementation; not a runtime dependency
├── README.md
├── TASKS.md
└── LICENSE
```

Keep command handlers small: they validate arguments and call a pipeline. Pipelines
coordinate providers and media processing; reusable operations should not live only
in development scripts. Ship templates with the CLI so installed commands do not
depend on a repository checkout. Copy required assets out of `outdated/` deliberately
rather than importing that directory at runtime.

## One directory per character

A character directory is the handoff between generation, animation, and downstream
tools. Its name is chosen by the user; filenames inside it do not repeat that name.

```text
hero/
├── character.json             # Versioned manifest; entry point for consumers
├── reference.png              # Optional normalized copy of the reference image
├── stills/
│   ├── S.png
│   ├── SE.png
│   ├── E.png
│   ├── NE.png
│   ├── N.png
│   ├── NW.png
│   ├── W.png
│   └── SW.png
├── animations/
│   ├── idle/
│   │   ├── S.png              # Horizontal strip: one row of animation frames
│   │   ├── S.webp             # Optional animated preview
│   │   └── …                 # Remaining seven directions
│   └── run/
│       └── …                 # Same layout as idle/
└── .sprute/                   # Optional working files; unnecessary for playback
    └── runs/
        └── <run-id>/          # Model responses, source media, extracted frames
```

`generate character --output ./output/hero` creates the manifest and eight stills.
`animate character --character ./output/hero --preset run` reads that manifest and
adds `animations/run/`. A newly generated character has an empty animation map;
it does not need an idle animation to be valid.

As described in the README, omitting `--output` targets the current directory.
The proposed writer should reject conflicting managed files rather than silently
replace an existing character. Generating another animation must preserve existing
stills and unrelated animations. Replacing an existing preset should require an
explicit overwrite option, whose CLI spelling remains to be defined.

## Directions and frames

Use uppercase compass names everywhere, with this canonical order:

```text
S, SE, E, NE, N, NW, W, SW
```

These names describe the character's facing direction: `S` faces toward the viewer
and `N` faces away. This preserves the previous implementation's direction order.
All eight directions are exported explicitly, including any produced by mirroring.

Each still is a transparent PNG. Each animation PNG contains the frames for one
direction, left to right, in playback order. For a frame size of `w × h` and `n`
frames, the strip is `(w × n) × h`; frame `i` starts at `(i × w, 0)`.
Directions are separate files, not successive animation frames in one strip.

Use one frame canvas and bottom-center anchor across the character's stills and
animations. Pad frames to that canvas instead of cropping each frame independently,
which would make playback jitter. If an animation cannot fit, require an explicit
canvas resize and rebuild rather than silently clipping it or changing its scale.

Trim the selected cycle before exporting a looping strip. Do not include a duplicate
closing frame. Within a preset, all directions share the same frame count and timing;
different presets may have different lengths. WebP previews must use the exported
frames and timing so they reflect the assets a game will play.

## Character manifest

`character.json` records the format version, frame geometry, asset paths, and timing.
All paths are relative to the character directory, so it can be moved or shared.
This is an illustrative manifest for a character with a completed run animation;
the dimensions and timing are examples, not defaults.

```json
{
  "version": 2,
  "name": "hero",
  "directions": ["S", "SE", "E", "NE", "N", "NW", "W", "SW"],
  "frame": {
    "width": 256,
    "height": 256,
    "anchor": [0.5, 1]
  },
  "reference": "reference.png",
  "stills": "stills/{direction}.png",
  "animations": {
    "run": {
      "strip": "animations/run/{direction}.png",
      "preview": "animations/run/{direction}.webp",
      "frameCount": 24,
      "frameDurationsMs": [
        42, 41, 42, 42, 41, 42, 42, 41,
        42, 42, 41, 42, 42, 41, 42, 42,
        41, 42, 42, 41, 42, 42, 41, 42
      ],
      "loop": true
    }
  }
}
```

`version` identifies the file format, independently of the CLI package version.
`anchor` uses normalized coordinates from the frame's top-left corner.
`{direction}` expands to each value in `directions`. Omit `reference` and `preview`
when those optional files are absent. `frameDurationsMs` contains one positive
duration per frame, preserving variable timing without rounding it to a single FPS.
`loop: true` means repeat indefinitely; `false` means play once.

Before accepting a character, validate its supported version, eight direction names,
positive integer dimensions and frame counts, timing array lengths, and referenced
files. Asset paths must stay inside the character directory. Stills must match the
frame size; strips must match the frame size multiplied by their frame count.

Write assets to a temporary run directory first. Add an animation to the manifest
only after all eight directions are complete and validated. Failed runs may retain
working files for diagnosis, but must not advertise incomplete assets as playable.
Never save API keys or authorization headers in the manifest or working metadata.

## Existing examples and remaining decisions

The current `examples/monet/` directory contains eight animated WebP files and a
README with their extraction details. It is a preview example, not yet a character
directory in this proposed format. The `.entity.json` and `.sprute.yaml` files in
`outdated/examples/` belong to the previous pipeline; no automatic migration is
implied here.

The initial format covers character stills and named animations. Default canvas
size, padding amount, overwrite and recovery flags, and migration support still need
implementation decisions. The planned `generate profile` command also needs its
output defined before adding a profile directory or manifest field.
