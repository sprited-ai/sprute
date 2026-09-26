# Export state strips in Comfy

Open `sprute-export-state-strips.json`. This is the tested postprocessing
companion to `sprute-animate-native-parity.json`; no diffusion model is run.

## Input contract

- Exactly 82 frames, 576×768 pixels, 3×3 grid with an unused center.
- Grid rows: `NW N NE`, `W empty E`, `SW S SE`.
- State ranges (zero-based, end excluded): idle `[0,30)`, walk `[30,62)`,
  run `[62,82)`. These are driver boundaries, not automatic loop detection.
- Update crop sizes, batch offsets and state ranges before using other layouts
  or frame counts. This fixed-layout graph does not validate that contract.
- Default input is the verified Comfy output uploaded to
  `input/sprute-native-192/native-comparison_00001_.webp` on gin.

The graph crops eight character batches before running BiRefNet ToonOut once
on their concatenated batch. ToonOut uses 512 processing resolution, foreground
refinement, zero blur/offset and alpha output. It then restores the eight batches
and concatenates corresponding frames horizontally; it never mixes times into
one still sheet. Default node names are preserved.

Outputs are three 1536×256 animated RGBA WebPs in `output/sprute/states/`:
`idle-horizontal`, `walk-horizontal`, `run-horizontal`. Direction order is
`S SE E NE N NW W SW`; each cell is 192×256. Quality 90, lossy, 24 fps setting.
The core saver stores 41 ms per frame at this setting; native CLI uses alternating
41/42 ms. Requires KJNodes and ComfyUI-RMBG alongside core nodes.

## Verified

Gin prompt `a17307a9-0501-485f-b245-7873287c0d76` completed in 23.99s.
All three outputs decoded as RGBA, 1536×256, with 30/32/20 frames and non-opaque
alpha. Group layout was added after this run without changing node parameters
or links. Existing main workflows remain unchanged.
