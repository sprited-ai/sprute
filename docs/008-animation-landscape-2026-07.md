# Research: animation options for multi-direction Sprute characters

> Decision-oriented survey, 2026-07-26. Scope: turn Sprute's existing
> 5-generated/8-output direction set into game-ready `idle`, `walk`, `run`,
> `attack`, and similar animation states. Sources include official model
> repositories and documentation, papers, reproducible GitHub workflows, and
> practitioner reports. Community reports are treated as hypotheses until
> reproduced on Sprute inputs.

## Executive finding

There is still no single model that demonstrably solves all of:

1. exact character and style preservation,
2. exact motion and facing control,
3. synchronized phases across 5 or 8 directions,
4. a genuinely periodic loop,
5. temporally stable RGBA,
6. permissive local deployment.

The strongest route is therefore a **motion-controlled pipeline with explicit
post-processing**, not prompt-only image-to-video:

```text
directional character still
  + direction-matched motion driver
  -> controlled animation model
  -> cycle/phase alignment
  -> temporal matting
  -> anchor/scale normalization
  -> frames + atlas + metadata
```

The newest first candidate is **SCAIL-2**, followed by **SteadyDancer** and
**Wan2.2-Animate**. A separate **Wan I2V + VACE** pipeline is the important
fallback because a sprite-specific community implementation found it more
faithful than Wan2.2-Animate for locked base animation.

For a commercial quality ceiling, test **Kling Motion Control**. Treat
Seedance 2 and Veo 3.1 as general I2V/reference-video controls rather than the
primary deterministic motion-transfer path.

## Executed Sprute smoke test

The first same-input test is recorded in
`experiments/007-animation-provider-smoke/`. It used one E-facing pixel-art
fairy and one four-second illustrated motion driver, then mirrored both inputs
for a W follow-up on the viable routes.

- **Seedance 2.0 Fast won this input.** It preserved the pixel style and fixed
  side orientation best in both E and W.
- **Local SCAIL-2 was the strongest literal motion follower** and ran in about
  50 seconds, but repainted the sprite and followed the driver's unwanted yaw.
- **Hosted SCAIL-2 failed the usable-quality gate** with green contamination,
  deformation, and an unexpected 896x512 output.
- **Kling v3 rejected the illustrated driver** because its preprocessor could
  not detect a complete upper body; no quality comparison was possible.

This changes the immediate order for Sprute inputs: advance Seedance to the
direction test, retain local SCAIL-2 as the open baseline, and treat the paper
ranking below as a candidate landscape rather than the observed winner.

## Candidate landscape

### Tier A — test first

#### SCAIL-2

- Released June 2026; official code and weights.
- Apache 2.0.
- Based on Wan2.1, but conditions directly on driving video rather than
  reducing all motion to a 2D skeleton.
- Supports animation, replacement, animals/non-human drivers, multi-character
  cases, and multi-reference input.
- Multi-reference is particularly relevant to Sprute: front, back, and
  diagonal stills can supply appearance details hidden in a single view.
- Runs at 512p or 704p; official ComfyUI integration exists.
- Correct masks are still critical. The official documentation warns that a
  wrong mask can collapse animation mode into replacement behavior.
- Very new: community workflows and operational knowledge are still unstable.

Sources:
[official repository](https://github.com/zai-org/SCAIL-2),
[paper](https://arxiv.org/abs/2606.10804),
[early ComfyUI report](https://www.reddit.com/r/comfyui/comments/1u3b76b/scail2_workflows_for_comfyui/).

#### SteadyDancer

- Apache 2.0; official code, weights, GGUF, and ComfyUI workflows.
- Uses an I2V formulation specifically to preserve the exact first frame.
- Includes pose alignment intended to handle mismatched proportions and a
  temporal start gap between the still and the driving video.
- This directly targets a common Wan Animate failure: stretching legs or
  changing the face when driver/reference sizes differ.
- Still fundamentally human-pose oriented; highly stylized or non-humanoid
  Sprute characters may break pose extraction.
- Official single-GPU output example is 1024x576 from a 14B model.

Sources:
[official repository](https://github.com/MCG-NJU/SteadyDancer),
[paper](https://arxiv.org/abs/2511.19320),
[community comparison](https://www.reddit.com/r/StableDiffusion/comments/1pesv0n/zimage_turbo_steadydancer/).

#### Wan2.2-Animate-14B

- Apache 2.0; official character animation and replacement model.
- Native ComfyUI and Diffusers support; the most mature open baseline here.
- Takes a character image and driving video and transfers holistic body and
  expression motion.
- Strong community evidence for motion transfer, but also repeated failures:
  identity softening, background/brightness shifts, proportion changes, and
  sensitivity to the first frame and mask.
- Reference and driver should match orientation, crop, body coverage, scale,
  and position as closely as possible.

Sources:
[official repository](https://github.com/Wan-Video/Wan2.2),
[ComfyUI announcement](https://www.reddit.com/r/comfyui/comments/1notl47/),
[input-alignment failure report](https://www.reddit.com/r/comfyui/comments/1utn1va/official_wan_22_animate_character_replacement/).

#### Wan2.2 I2V + Wan2.1 VACE

This is not one model but the most relevant reproducible sprite pipeline found:

1. Qwen Image Edit + OpenPose creates a posed seed frame.
2. Quantized Wan2.2 I2V generates the base animation.
3. BiRefNet removes the background.
4. Wan2.1 VACE inpaints cosmetic layers while preserving base motion.
5. SAM segments aligned hair, eye, and clothing layers.

The MIT-licensed implementation runs on a 24GB RTX 3090, with about 80–120GB
of model storage. It has been validated on one character for idle, walk, and
in-air animation. It has **not** demonstrated synchronized multi-direction
animation. Its author initially tried Wan2.2-Animate but switched because it
did not follow the base animation closely enough.

Sources:
[Reddit write-up](https://www.reddit.com/r/comfyui/comments/1sve5id/one_image_in_2d_animated_and_customizable/),
[reproducible repository](https://github.com/mor-o/comfyui-2d-character-pipeline).

### Tier B — closed quality controls

#### Kling Video Motion Control

- Explicit driving-video + character-image motion transfer.
- Crucially exposes two orientation policies:
  `matches video` and `matches image`.
- `matches image` is directly useful for holding a Sprute direction while
  borrowing the driver's motion.
- Official guidance confirms the same alignment constraints seen in Reddit:
  full body must match full body, the character must stay visible, use one
  continuous fixed-camera shot, and avoid overly fast motion.
- Closed and credit-based. The official documentation currently describes
  3–30 second inputs, which is wasteful for a one-second sprite cycle.

Source:
[official Motion Control guide](https://kling.ai/quickstart/motion-control-user-guide).

#### Runway Act-Two

- Dedicated performance capture with a driving video and character image.
- Works across styles, angles, and some non-human characters.
- API access exists and costs 5 credits/second with a 3-second minimum.
- Poor fit for Sprute's default mode: it automatically introduces
  environmental motion, may add handheld camera motion, and recommends
  waist-up character material. Useful for expressive greet/dialogue states,
  not the first walk-cycle candidate.

Sources:
[official guide](https://help.runwayml.com/hc/en-us/articles/42311337895827-Performance-Capture-with-Act-Two),
[API endpoint](https://dev.runwayml.com/endpoints/character_performance?modelId=act_two).

#### Seedance 2 / Veo 3.1

- Seedance 2 accepts image, video, audio, and text reference material.
- Veo 3.1 accepts up to three reference images and supports first/last frames.
- Both are valuable quality bars, but neither exposes the same explicit
  direction-retention contract as Kling Motion Control.
- Keep them in the smoke test only if access and minimum cost are reasonable.

Sources:
[Seedance 2 paper](https://arxiv.org/abs/2604.14148),
[Runway model inputs](https://docs.dev.runwayml.com/assets/inputs/),
[Veo 3.1 API](https://ai.google.dev/gemini-api/docs/video).

### Tier C — observe, do not lead with

- **SCAIL 1:** useful 3D-consistent pose controls and Blender-rig input, but
  superseded for the main experiment by SCAIL-2.
- **LTX-2.3:** fast local I2V and LoRA support, but not specialized for exact
  character motion transfer; its model weights use a custom community license.
- **HunyuanVideo 1.5:** official I2V and LoRA training, but a general video
  model under a Tencent community license.
- **StableAnimator / MultiAnimate:** valuable pose-animation research, but
  less operationally mature and human-centric.
- **Wan-Alpha:** generates native RGBA video and is MIT-licensed, but as of
  2026-07-26 the official repository still lists I2V weights as unreleased.
  It cannot yet preserve an existing Sprute character from a still.

Wan-Alpha source:
[official repository](https://github.com/WeChatCV/Wan-Alpha).

## Sprite-native products and competing workflows

### PixelLab

PixelLab is the closest product-level benchmark:

- 4/8-direction rotation from one character;
- direction-aware animation generation;
- text and skeleton animation;
- transparent output;
- Aseprite and Pixelorama integrations.

Its own rotation guide recommends manual correction and iterative inpainting,
which is important evidence that multi-view consistency remains unsolved even
in a specialized product. Its current animation limits are pixel-art focused:
up to 256x256 input, with 16 output frames only at 32/64px and four frames at
larger sizes.

Sources:
[rotation documentation](https://www.pixellab.ai/docs/tools/rotate),
[animation documentation](https://www.pixellab.ai/docs/tools/animate-with-text-pro).

### SpriteBrew and other hosted tools

SpriteBrew is an AGPL web product using Retro Diffusion APIs, with 4-angle and
8-direction presets and multiple game-engine exporters. Autosprite, GameLab
Studio, Sprite AI, and similar products make comparable claims but publish
little model/evaluation detail. They are useful black-box product benchmarks,
not evidence for a Sprute implementation.

Source:
[SpriteBrew repository](https://github.com/GAlbanese09/spritebrew).

### 3D-to-sprite

Practitioner discussions repeatedly converge on 3D rendering when exact
multi-direction consistency matters:

```text
concept -> 3D mesh -> rig -> one animation -> render N cameras -> sprites
```

This gives exact phase, direction, camera, anchor, and alpha consistency, at
the cost of converting the character to 3D. It should be retained as a
deterministic control and possibly as a motion-driver generator, even when
the final appearance is regenerated in 2D.

Sources:
[8-direction workflow discussion](https://www.reddit.com/r/aigamedev/comments/1suxtxm/what_is_your_process_to_generate_animations/),
[3D driver into Wan Animate](https://www.reddit.com/r/comfyui/comments/1ojbuyt/new_experiments_with_wan_22_animate_from_3d_model/).

## Multi-direction design

### Do not generate one independent prompt per direction

Independent prompt-only clips have no shared gait phase. Direction changes in
game will pop because frame 3 in `E` does not mean the same pose as frame 3 in
`NE`.

Use one canonical motion and derive direction-matched drivers:

```text
canonical walk rig / clip
  -> S driver
  -> SE driver
  -> E driver
  -> NE driver
  -> N driver
```

Each generation receives:

- the existing Sprute still for that direction;
- the driver rendered for the same direction;
- identical motion, cycle count, camera scale, and frame rate;
- fixed subject center and ground contact.

Generate `S`, `SE`, `E`, `NE`, and `N`; mirror the three western directions by
default. Provide `full-8` for asymmetric characters.

### Phase synchronization must be measured after generation

Even identical drivers do not guarantee identical output timing. Generative
models may delay, speed up, or omit a motion. Do not select frame `t` from
every direction and assume phases match.

Align every result back to the canonical cycle:

1. estimate output pose or motion features;
2. align them to canonical phases with dynamic time warping or cyclic search;
3. sample the same `contact/down/pass/up` phases;
4. store a shared phase index in metadata.

For humanoids, compare pose tracks. For stylized/non-human characters where
pose detection fails, use silhouette/optical-flow features plus the existing
luma autocorrelation and a manual-review fallback.

### Multi-reference use

SCAIL-2's multi-reference input should be tested in two modes:

1. **single-direction reference:** only the still matching the requested output;
2. **identity pack:** target direction plus front, side, and back Sprute stills.

The second may preserve hidden costume details, but may also leak the wrong
orientation. It is an experiment, not an assumed win.

## Loop generation

Do not force an identical standing first and last frame. Both Sprute's
existing experiment and community reports observe that this often suppresses
motion or produces a stop/start seam.

Preferred method:

1. request at least two continuous cycles;
2. detect the periodic interval after generation;
3. select one cycle whose start and end have matching pose **and velocity**;
4. resample to the target frame count;
5. score both pixel/feature seam and motion-derivative seam.

First/last-frame or VACE loop closure is a repair path, not the default. A
pixel-identical first/last frame can still look wrong when velocity drops to
zero at the boundary.

Community evidence:
[Wan2.2 loop discussion](https://www.reddit.com/r/StableDiffusion/comments/1r72v4f/can_you_make_a_seamless_loop_with_the_first_and/).

## Transparency

### Current production choice

Use a temporal video-matting path:

- **Baseline:** existing ToonOut/BiRefNet per frame.
- **Candidate:** SAM2Matting or MatAnyone-class tracked video matting.
- **Fallback:** flat chroma background + ToonOut + temporal alpha smoothing.

Per-frame BiRefNet has good anime edges but can shimmer. Tracking-based video
matting is designed to maintain temporal identity while resolving hair and
fine edges.

Sources:
[SAM2Matting paper](https://arxiv.org/abs/2606.27339),
[Sprited BiRefNet video behavior](https://replicate.com/sprited/birefnet-video/readme).

### Do not rely on double generation over white/black

Alpha-from-white/black compositing only works if foreground RGB and geometry
are identical in both renders. Two independent stochastic video generations
do not meet that condition. It is valid only if a single locked foreground
render can be composited onto two backgrounds, in which case the foreground
is already available. Keep this out of the default plan.

### Future native RGBA

Wan-Alpha is relevant once its I2V weights are released. Today it is a
text-to-RGBA model and therefore cannot reliably animate an existing Sprute
identity.

## Smoke-test protocol

Use one existing illustration-style Sprute character with visible asymmetric
detail. Start with `walk/E`; do not spend five directions on every candidate.

### Round 0 — deterministic/product controls

1. Existing Seedance 1 and Veo 3.1 artifacts.
2. PixelLab direction-aware animation, if a small paid test is available.
3. 3D driver rendered directly to frames.

### Round 1 — one run each, same E input

1. SCAIL-2, single reference.
2. SCAIL-2, multi-reference identity pack.
3. SteadyDancer.
4. Wan2.2-Animate.
5. Wan2.2 I2V + VACE sprite pipeline.
6. Kling Motion Control with `orientation matches image`.
7. Seedance 2 reference-to-video, if accessible.

This is a smoke test, not a ranking. Any stochastic candidate that passes goes
to three fixed seeds in Round 2.

### Round 2 — finalists, three seeds

Reject a candidate before multi-direction expansion if it:

- changes signature clothing, hair, face, weapon, or proportions;
- fails to remain in-place or changes camera;
- fails to complete two recognizable cycles;
- cannot yield one clean periodic cycle;
- produces frame-level limb mutations after sampling;
- requires manual work that cannot be encoded as a repeatable rule.

### Round 3 — directional expansion

Run finalists on `S`, `SE`, `E`, `NE`, and `N`, using direction-matched drivers.
Then test mirrored west directions and one asymmetric `full-8` case.

## Evaluation scorecard

Automated scores are filters; final approval must inspect the sprite animation
at its actual in-game size.

| group | weight | measurements |
|---|---:|---|
| identity/style | 25 | masked visual embedding similarity, palette drift, silhouette/proportion drift, signature-detail checklist |
| motion | 20 | driver pose/flow agreement, foot sliding, readable contact/pass poses |
| directional coherence | 20 | facing correctness, shared phase agreement, cross-view scale and silhouette consistency |
| loop | 15 | endpoint visual distance, velocity discontinuity, periodic residual |
| extraction | 10 | alpha-edge quality, temporal shimmer, clipped pixels |
| operations | 10 | seconds, peak VRAM, disk, API cost, failure/retry rate, license |

Store raw clips, extracted frames, alpha previews, prompts, masks, model hashes,
seeds, timings, and scores. A comparison sheet should show the same phase
across all directions, not merely one animated preview per direction.

## Recommended decision

### Immediate

Build no production integration yet. Reproduce:

1. SCAIL-2;
2. SteadyDancer;
3. Wan2.2-Animate;
4. the MIT Wan I2V + VACE sprite pipeline;
5. Kling as a closed quality bar.

Use the same direction-matched 3D driver for all motion-transfer candidates.

### Likely architecture

Keep the model behind an animation-provider boundary:

```ts
interface AnimationProvider {
  animate(input: {
    character: RawImage;
    identityReferences?: RawImage[];
    motion: Video;
    direction: Direction;
    state: AnimationState;
    seed?: number;
  }): Promise<GeneratedClip>;
}
```

Then make cycle alignment, temporal matting, normalization, packing, and
metadata provider-independent. The durable value is the test corpus, driver
library, extraction/evaluation pipeline, and directional phase contract—not
whichever video model wins in July 2026.

### Current ranking to test, not a claimed quality ranking

1. **SCAIL-2** — best feature/license fit; newest and least operationally proven.
2. **SteadyDancer** — strongest first-frame preservation hypothesis.
3. **Wan2.2 I2V + VACE** — closest reproducible sprite-specific implementation.
4. **Wan2.2-Animate** — mature open baseline.
5. **Kling Motion Control** — closed quality ceiling and explicit orientation control.
6. **PixelLab** — closest sprite-native product benchmark, especially for pixel art.

The ranking must change based on Sprute's own extracted-frame results, not on
paper videos, vendor showcases, or Reddit votes.
