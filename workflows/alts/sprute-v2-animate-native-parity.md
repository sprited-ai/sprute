# Native / Comfy inference comparison

Open `sprute-v2-animate-native-parity.json` on gin's ComfyUI. This is a comparison
workflow, not a replacement for the full character workflow.

It reuses native-prepared inputs copied into
`/home/gin/dev/ComfyUI/input/sprute-native-192/{driver,driver-mask}`.
These copies are independent of disposable native experiment outputs.
Reference and reference-mask PNGs are uploaded under Comfy's `input/sprute-native-192/`.
On another machine, copy those prepared assets and change the two folder paths.
Requires VideoHelperSuite's `VHS_LoadImagesPath`; other nodes are Comfy core.

Settings: 576×768; 85 inference frames; seed 42; 8 steps; CFG 1; shift 5;
UniPC/simple; empty prompts; animation mode; DPO 1.0; LightX2V 0.8.
Uses the existing FP16 SCAIL2 checkpoint and FP8 UMT5. Comfy's automatic model
casting is not an assertion of identical native BF16/FP8 execution.

`ImageFromBatch` retains frames 0–81; saved RGB WebP is 24 fps, lossy quality 90.
No ToonOut or state splitting is included here. Native initial noise and sampling
schedule differ from Comfy, so equal seed/settings do not promise equal pixels.
Gin's current core WebP saver uses `int(1000 / fps)` milliseconds per frame:
24 fps becomes 41 ms, whereas the CLI alternates 41/42 ms to preserve elapsed
time. Expect 3,362 ms versus 3,417 ms for 82 uncoalesced frames. This is an
export timing difference, independent of inference quality.

GPU execution succeeded on gin (prompt `ac34a285-fc5c-47e4-82d5-950afbf07b73`),
with 208.43s between Comfy execution start and success. The decoded output is
576×768, 82 frames, 3,362 ms, 2,805,936 bytes. Saved at
`ComfyUI/output/sprute/native-comparison_00001_.webp`.
Visual review of all 82 north-tile frames found no full front-facing flip.
Idle/walk retain a rear three-quarter bias; run changes head angle and hair
shape, with a small artifact above the head in some frames. This is one seed,
not exact eight-direction fidelity or a general success-rate measurement.
Native runtime FP8 and this Comfy run also differ in execution precision, so
the timings are not a controlled backend speed comparison.
