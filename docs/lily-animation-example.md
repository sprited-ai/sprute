# How the Lily walking preview was made

The current [Lily preview](../experiments/178-lily-refined-game-export/preview.html)
shows AI-generated sprite frames following a walking animation from a 3D rig.
Lily herself was not rigged. The browser plays saved images; it runs no AI model.

1. **Start with Lily's eight standing views.** The source is the wingless
   [Lily image strip](../examples/lily.spritesheet.png).
2. **Render a walking guide.** Blender renders a Quaternius character's
   `Walk_Loop` from eight camera directions. This supplies the movement.
3. **Generate Lily walking.** SCAIL-2 takes each Lily reference and its matching
   motion guide to generate a video for that direction.
4. **Remove the background.** ToonOut estimates transparency. An experimental
   PyMatting pass refines the edge transparency and foreground colors.
5. **Pack the pictures.** We select32 frames per direction and place the resulting
   256 images in128px cells, preserving their recorded timing.

## Which model?

The saved workflows use **SCAIL-2 based on Wan2.1**, with the checkpoint
`wan2.1_14B_SCAIL_2_fp8_scaled.safetensors`. This is a different workflow from
**WAN Animate**. Seedance was used in earlier experiments; it did not generate
the frames in this preview.

All eight saved workflows were checked against their recorded SHA256 hashes and
share these settings: seed7,40 steps, CFG3, UniPC sampler, simple scheduler,
denoise1. They use `umt5_xxl_fp8_e4m3fn_scaled.safetensors` for text,
`clip_vision_h.safetensors` for image conditioning and `wan_2.1_vae.safetensors`.
These are the settings of this example, not a guarantee for other characters.

## Can I make my own this way?

The parts exist in the development checkout, but this is still an experimental
workflow. `prepare-animation --scail-masks` and `plan-animation --model scail2`
now prepare the inputs and build the SCAIL-2 graph. The generic prompt differs
from this example's handcrafted caption. Frontal, right-side and rear Lily runs
completed; reviewed images preserve recognizable appearance with redrawn details.
The rear result exaggerates pale shorts pockets and its gait remains unaccepted.
The other five directions remain untested through the generic planner. The
[motion renderer](../motion/README.md) can now create RGB guides and all eight
mask videos together using `--scail-masks`. Upload that bundle with
`upload-animation-drivers` and pass its output to the SCAIL planner.
Server setup still requires separate work. Published 0.4.1 creates standing views;
a beginner-ready generation workflow is still missing.

Once you have eight extracted and matted cycle folders named S/SE/E/NE/N/NW/W/SW,
the development commands can pack and preview them:

```sh
node dist/cli.js pack-animation my-cycles --size 128 --loop -o my-walk
node dist/cli.js preview-animation my-walk -o my-walk.html
```

These commands do not generate the missing frames. See the
[development guide](animation-development.md) for the individual tools.

The preview looks promising at game size, but some clothing details change between
directions and one NW frame has a smeared toe. Contact, cross-direction gait phase,
loop quality and transparency across different characters remain unresolved.

## Files behind the example

- Rigged motion: [070](../experiments/070-portable-motion-drivers/README.md).
- Generated directions: [S](../experiments/142-lily-scail-front/README.md),
  [SE](../experiments/152-lily-scail-se/README.md),
  [E](../experiments/143-lily-scail-side/README.md),
  [NE](../experiments/153-lily-scail-ne/README.md),
  [N](../experiments/149-lily-scail-rear/README.md),
  [NW](../experiments/154-lily-scail-nw/README.md),
  [W](../experiments/150-lily-scail-west/README.md),
  [SW](../experiments/155-lily-scail-sw/README.md).
- Transparency: [168](../experiments/168-lily-eight-direction-alpha/README.md),
  [174](../experiments/174-lily-sequence-refinement/README.md),
  [177](../experiments/177-lily-remaining-refinement/README.md).
- Current preview: [178](../experiments/178-lily-refined-game-export/README.md).

The later seed123 NW experiment180 is a separate comparison and is not included
in this preview.
