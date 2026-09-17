# What the experiments established

## Generation and motion

- Existing standing pipeline: Nano Banana Pro, `8dir-v1`, five generated directions plus mirrored NW/W/SW. This produces eight views, not eight independently inferred views.
- Mirroring also flips lettering and asymmetric hair/accessories. Elise's sweatshirt text visibly reverses in mirrored standing views. This needs an explicit product limitation or a true eight-view mode.
- Recent Seedance 2 run requests: 480p, 1:1, 5 seconds, seed 42, audio off. Decoded outputs were 640×640, 121 frames, 24fps. Expected cost was about $0.50 per request, not a verified invoice or permanent price.
- Elias and Elise run samples preserved the main front/back layout. This is sampled visual review, not a measured success rate. Seedance may change proportions, motion, clothing text and occlusion.
- SCAIL2 local experiment 473: 14B FP8, LightX2V strength 1, 8 steps, CFG1, shift1, UniPC/simple, seed42, 768×768, 65 frames at24fps; about110.4s. Positive prompt `8 directional character sprite animation`, negative empty. Good result from one seed is not general reliability evidence.
- 8-direction generation can fail on south/front versus north/back. Facial features help disambiguate intent but did not guarantee correct results in earlier tests.
- Ragnarok 2D drivers and early retargeted run rigs had issues. Do not treat them as validated presets. Kimodo contact-v4 became the accepted run driver.

## Drivers

Run rendering source: experiment477, based on experiment471/contact-v4. White/light blue body, warm head tint retained, gray #808080 background,15° orthographic camera,256×256 per direction,3×3 grid with empty center. Source run has25 frames at30fps; original composed driver65 frames at24fps.

New idle/walk driver assets were created by opening that same run render scene and replacing only target-rig local bone animation from existing baked scenes:

- Idle: experiment468/idle-driver,60 frames at24fps.
- Walk: experiment457/driver-shade75,32 frames at24fps.
- Rig rest matrices checked equal. Run object transform retained; donor object transform differs by a small translation. Materials, camera scale, lighting and mesh retained.
- Each preview WebP repeats one cycle. Each MP4 repeats motion for120 frames/5s. Walk32 does not divide120: this MP4 is reference footage, not itself certified seamless at its file boundary.

An earlier Elise idle request returned provider E005 (sensitive input or output). No video was produced and failure billing was not verified. The provider did not identify the reason. Driver color as cause is unproven. Rendering consistent drivers is separate from deciding whether a rejected hosted request may be resubmitted.

## Matting

The still Elise sheet used per-view floodfill, NOT ToonOut. Be explicit about this distinction.

For animation: split the grid into eight cells FIRST, run BiRefNet_toonout on each frame of each direction, THEN compose outputs. Tested ComfyUI settings: process_resolution1024,mask_blur0,mask_offset0,refine_foreground=true,background=Alpha. No extra blur/erosion was needed for these samples. Foreground refinement helps with gray edge contamination; review on both light and dark backgrounds.

Use original decoded video frames for matting, not an already lossy preview whenever possible. Later Elise run/walk scripts upload a lossless animated WebP for this reason. The earlier Elias processing used a Q80 intermediate.

## Layout and export

- Grid: NW N NE / W empty E / SW S SE.
- Horizontal: S SE E NE N NW W SW.
- Elise standing sheet2560×512; each cell320×512(width×height), no inter-cell gaps. Transparent margins are INSIDE the cells.
- Reference construction shrank each standing cell to160×256 and placed it at x48 in a256×256 square. Grid768×768 became output640×640.
- Inverting that placement restores layout, not character scale: measured front still alpha height376px, run410–437px after inversion. Matching canvas sizes does not mean matching character size.
- Per-direction bounding-box crops produced unequal cell widths and excessive density. Preserve a fixed per-state layout, common scale, and baseline. Never normalize every frame independently: it destroys motion and causes jitter.
- Run loop detection found19-frame recurrence. Best Elise boundary window was frames23..41 inclusive;19frames/~792ms. This is measured on that output only, not a universal preset.
- Lossy WebP Q65 greatly reduces file size. Preserve alpha,24fps via alternating41/42ms durations, and explicit infinite loop. Avoid repeated lossy transcoding.

## Product / engineering

Expose common motion presets first; custom motion/Kimodo is a later integration. Record exact inputs before submitting and resume prediction IDs to avoid duplicate billing. A prompt, seed and model name alone are insufficient for reproduction.

Current experiment scripts are not `sprute animate character --preset run`. Do not present proposed v2 syntax as an already-tested command.

One incorrect `sprute build <config>` invocation was parsed as a text prompt and started the configured Gemini path; it was interrupted. Its billing was not verified. Correct legacy invocation was `tsx src/cli.ts /absolute/path/elise-build.json`. CLI should reject unknown verbs instead of accidentally triggering paid generation.
