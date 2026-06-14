# Research: beyond NBP — open generation + fine-tuned animation

> Research agenda + learnings, 2026-06-13. Two bets, both pointing away from
> closed APIs toward open models we can fine-tune on our own hardware
> (`ssh gin` = 96GB VRAM, or RunPod). Captures the direction from Jin's
> session and the hard-won learnings already banked in the SpriteDX repos and
> this repo's `experiments/005`.

## Why move off Nano Banana Pro

NBP carries M1 ([`003`](003-cli-prompt-first.md)), but it has real limits for
*character* art:

- **Optimizes "make sense" over "예쁨" (beauty).** Outputs are coherent but
  stale/cliché — competent, not striking.
- **Takes the template's edge conditions too literally.** The worked-example
  lines/layout are obeyed rigidly, which flattens the result and limits style.
- **Not pretty enough.** The best illustration work (e.g. top Instagram
  artists) is *not* coming from Flux either — it's coming from the
  Civitai/community anime-model ecosystem.
- **FLUX.1 Pro Fill** felt aesthetically better than NBP in testing — but Flux
  (and NBP) are **expensive** closed APIs.

→ **We need an open-source character-generation model**, ideally fine-tunable,
and the best of those live on **Civitai**. Two research tracks follow.

---

## The moat (the actual goal)

The base model is **commodity** — anyone can download Z-Image, Wan2.2, an
Illustrious checkpoint. Picking "the best model" is the *start*, not the moat.
The moat is what we build on top, and how **repeatably** we can rebuild it:

1. **Proprietary dataset** — the real asset. Our own sprite/turnaround corpus +
   8-direction / animation-state labeling + curated motion references we build
   for fine-tuning. Others can't copy what they can't see.
2. **Fine-tuned models on it** — a generation LoRA/FT (aesthetic + character
   identity) and a Wan2.2 animation LoRA (Seedance-quality locomotion). The
   weights are ours; the base is swappable underneath.
3. **The reproducible pipeline** — `sprute`: reference → consistent 8-dir
   sprites → animation states → clean RGBA extraction. Encoded as code, not
   tribal knowledge.
4. **An eval harness** — scores aesthetic quality, 8-direction consistency, and
   gait quality, so "best model" is *measured*, not vibes. This is what makes
   the search repeatable and the moat defensible.

**"Repeatable" = versioned datasets + training configs + eval, re-runnable on
`gin`/RunPod.** As base models improve (Z-Image → whatever's next), we re-train
and keep the lead — the dataset, recipe, and pipeline transfer, so the moat
**compounds** across base-model generations instead of resetting. What is *not*
the moat: a closed API, the public base weights, or a one-off hand-tuned output.

**Build order:** eval harness first (so every model claim is measured) →
candidate bake-off → fine-tune the winner on our data → fold into `sprute`.

---

## Track A — open character generation (replace NBP)

Goal: generate the base character / reference at higher aesthetic quality than
NBP, from an open model we can run and fine-tune ourselves.

### Civitai candidate landscape (anime/illustration, 2026)

| model | base | note |
|---|---|---|
| **Z-Anime** ("zanime") | Alibaba **Z-Image** (S3-DiT, 6B) | Full anime fine-tune; 8-step distill ~20s on consumer HW; AIO/GGUF. **Jin's pick to test first** for reference-character generation. |
| **Illustrious XL** | SDXL | Cleaner line work, strong prompt adherence, top-rated anime base |
| **NoobAI XL** | Illustrious + v-pred | More stylistic range, strong composition; large booru knowledge |
| **Pony Diffusion XL** | SDXL | Distinctive default style, huge LoRA ecosystem |

First experiment: **generate our reference characters with Z-Anime** and judge
aesthetic feel + usability vs NBP. Then survey the others on the same prompts.

### Generation is pluggable pipelines — NBP-template is just one

The NBP reference-fill-into-a-labeled-template flow (pattern-completing the
worked example — the "edge condition" it takes too literally) is **one optional
pipeline, not the architecture.** `sprute` should treat generation as
**pluggable pipelines**, NBP-template being one peer among:

- **NBP template-fill** (today) — cheap 8-dir consistency, but stale/literal.
- **Open inpaint/fill** — open inpaint model (FLUX.1 Fill is the closed
  reference for the *feel*) + ControlNet, keeping a template-style layout.
- **t2i + consistency** — character-locked open model (LoRA / IP-Adapter /
  reference-only) generating directions directly, consistency solved separately.
- **Fine-tuned house model** — our own LoRA/FT that bakes in identity + style
  (the moat path; may make the template unnecessary).

Each pipeline is a strategy with its own quality/cost/consistency profile; the
research picks winners per use-case rather than forcing one. NBP's biggest win
to preserve somewhere: **cheap multi-direction consistency.**

### Fine-tuning feasibility

Z-Image (6B) and SDXL-class models are well within `gin`'s 96GB; LoRA training
is cheap, full fine-tune feasible on this hardware or RunPod. A character/style
LoRA is the obvious lever for both "캐릭 느낌" (identity) and a non-stale house
style.

---

## Track B — animation states via video (Seedance quality bar)

Goal: walk / run / dance / idle / attack animation states for a character,
**at Seedance 1 Pro quality**, ideally from an **open, fine-tuned model**.

### The bet: fine-tune Wan2.2

Seedance 1 Pro is the quality bar but it's a closed API. **Wan2.2** (Alibaba,
open) is the candidate to fine-tune up to that bar for our specific task
(stylized character locomotion, in-place, looping), while preserving the
character's identity ("캐릭은 마치 캐릭 느낌으로").

- **Fine-tuning is feasible.** Wan2.2 I2V LoRA trains on a single GPU; tooling
  exists: **Musubi-tuner, AI Toolkit, diffusion-pipe, DiffSynth-Studio**, and a
  hosted `fal-ai/wan-22-image-trainer`. Note Wan2.2's MoE split: **both the
  high-noise and low-noise experts need their own LoRA**, used together at
  inference.
- **Today's gap (un-tuned):** Wan2.2 = frame-precise control, ~25% cheaper,
  runs locally; Seedance 1 Pro = higher res, longer, premium motion quality.
  Fine-tuning aims to close the motion-quality gap for *our* narrow domain.
- **Dataset:** a purpose-built motion set — reference locomotion clips paired
  with our character sprites, labeled by state (walk/run/dance/idle) and gait
  phase. Built fresh for this; the dataset is the moat ([the moat](#the-moat-the-actual-goal)).

### What "good" requires (from exp 005, Seedance vs Veo)

`experiments/005` already turned one NBP turnaround cell (E-facing) into a walk
cycle via both Seedance (Replicate) and Veo (Gemini):

- Seedance kept **style fidelity better** (chunky proportions, flat cel look);
  Veo had **better gait** (big clear strides, exact 1.00s period) but slimmed/
  re-rendered the character. A fine-tuned Wan2.2 should aim for *both*.
- **`first=last` standing frame pins motion dead** → idle wave, not a walk.
  Drop the last-frame constraint; prompt "marching in place, knees lifting
  high, arms swinging."
- `camera_fixed: true` (Seedance) / "no camera movement" (both) is essential —
  the subject must stay centered for grid extraction.

---

## What we already know — banked learnings (SpriteDX + exp 005)

Grounded pointers, so we don't re-learn these:

**Seedance pipeline (production, SpriteDX):**
- Model `seedance-1-0-pro-250528`; `camera_fixed:true`, `aspect_ratio:"1:1"`,
  `resolution:"480p"`, `duration:5`, `watermark:false`, `seed`. — `sprite-dx/ui/public/pipelines/character/v1/workflows/sprite-dx-v1-stage-2.json`
- **Structured XML shot-graph prompts**, not freeform: `<shot loop duration alt
  tags><character state direction .../></shot>`; `alt` carries the real motion
  cue ("at least two full cycles", "gentle breathing", "in-place"). — `sprite-dx/ui/worker/lib/pipeline-scripts.ts`, `sprite-dx-secondary/.../animationPrompt.v1.3.0.js`
- Standard states: greet (no loop), idle (loop), run (loop); ~1s/shot. Frame
  timing baked into `entity.json` (idle first frame 2000ms hold, rest ~42ms/24fps).

**Multi-shot & loop extraction:**
- Seedance returns **one concatenated video** for multi-shot prompts → needs
  **shot-boundary detection** (PySceneDetect alone fails: smooth idle→run
  transitions score low, running's high motion isn't a cut; semantic clip-vs-
  prompt scoring + HMM proposed). — `sprite-dx-secondary/docs/shot-boundary-detection.md`
- **`extract_loop_v2.py`** (production): best seamless loop via composite-frame
  cosine similarity + motion-energy correction + length penalty; motion-energy
  calibration (breathing 0.56, wave 0.97, run 15.0). — `sprited-comfyui-nodes/src/sprited_nodes/extract_loop_v2.py`
- Our `experiments/005/assemble.mts`: simpler autocorrelation gait-period
  detection on 8× downsampled luma, pick 8 frames across one period, key, center.

**The transparency blocker (CRITICAL):**
- **No video model emits RGBA.** Working trick: render the same animation on
  **white and black backgrounds, compute alpha from the difference** —
  clean transparency, no halos. Costs **2× generations per state**. — `sprite-dx/docs/june-2026-reddit-signal.md`
- Alternative: **BiRefNet-Temporal** matting — BiRefNet on sparse keyframes +
  RAFT optical-flow propagation (2–2.85× faster than per-frame, IoU 0.977,
  −17% temporal flicker). ToonOut variant for anime edges. — `birefnet-temporal/docs/temporal-roadmap.md`, `birefnet-video/README.md`

**Ops/cost:**
- Seedance ~$0.4/5s, Veo ~$0.6/4s (exp 005). Replicate **throttles hard under
  $5 credit** (6 req/min, burst 1). SpriteDX rate-limits Seedance to ~2 req/min.
- Per-character walk set ≈ 5 directions (S/SE/E/NE/N + mirror) ≈ $2–3 on Seedance.

---

## Experiments to run

Track A (generation):
1. Generate reference characters with **Z-Anime**; judge feel vs NBP (same prompts).
2. Survey Illustrious XL / NoobAI XL / Pony on the same set; rank aesthetics.
3. Test the **fill/inpaint fork**: open inpaint model + template → does the
   template trick survive with better aesthetics than NBP?
4. Train a **style/character LoRA** on `gin`; measure identity + de-staling.

Track B (animation):
5. Baseline: Wan2.2 I2V (un-tuned) on the exp-005 input; compare to Seedance/Veo.
6. Assemble a small **fine-tuning dataset** (motionseed.1 + our sprites) for
   walk/run/dance, in-place, looping.
7. LoRA fine-tune Wan2.2 (both noise experts) on `gin`/RunPod; iterate toward
   Seedance-quality motion **with character identity preserved**.
8. Integrate the **white/black alpha trick** or BiRefNet-Temporal into the
   extraction so animated sprites come out RGBA cleanly.

## Hardware & infra

- **`ssh gin`** — 96GB VRAM. Local fine-tune (LoRA, likely full for 6B) +
  inference for Z-Image/SDXL-class and Wan2.2.
- **RunPod** — burst capacity for bigger runs / parallel sweeps.
- See [Infra & accounts](../) memory: HF `sprited`, ToonOut ONNX, `comfy.sprited.ai`.

## Open questions

- Fill/inpaint vs t2i+consistency for multi-direction generation (Track A fork).
- Can a fine-tuned Wan2.2 actually reach Seedance motion quality for stylized
  sprites, or is the ceiling lower? (Bet, not proven.)
- Best open path to RGBA animation: 2× white/black renders vs BiRefNet-Temporal.
- Does fine-tuning let us *drop the template trick entirely* (a character LoRA
  generating consistent directions directly)?

## Research findings & recommendation (2026-06-13, deep-research)

Deep-research pass: 5 angles, 25 sources fetched, 109 claims → 25 adversarially
verified (18 confirmed, 7 killed). **The single most important finding is a
negative one:** *nothing in the corpus benchmarks any open model's anime
aesthetic against NBP, nor any open I2V model's stylized-2D locomotion against
Seedance.* Every aesthetic/quality claim is a vendor card or a practitioner
blog. So research **narrows the field to test — it does not pick the winner.**
That is exactly why the eval harness is the first build.

### Part A — generation (verified)

- **Z-Image (Alibaba Tongyi-MAI)** — genuinely **Apache 2.0** (commercial-safe,
  unlike FLUX dev), 6B non-distilled, authors explicitly position it for *LoRA +
  ControlNet*, runs/LoRA-trains in ~16GB, hundreds of Civitai LoRAs already.
  Anime competence is a **model-card claim, not benchmarked.** Weak spot:
  ControlNet is only an immature **model-patch** with reported quality issues.
- **SDXL anime stack (Illustrious XL / NoobAI-XL / Pony V6)** — the de-facto
  proven-aesthetic local anime stack (curated guides still recommend only these,
  not FLUX/Z-Image/Qwen), cheapest LoRA (8–16GB), richest control (ControlNet,
  IP-Adapter, inpaint). Illustrious = neutral base, *derivatives outperform it*;
  NoobAI = ~13M Danbooru+e621, v-pred variant (better adherence/color).
- **FLUX.1-Fill-dev + FluxFillControlNetInpaintPipeline** — cleanest single-pass
  mask-fill + ControlNet (the literal template-fill pattern), but **non-commercial
  license** and a maintainer note its output isn't yet on par with Qwen-Edit/Kontext.
- **Qwen-Image 2512** — decent anime, **Apache 2.0**, but 20B/~41GB → LoRA ≥24GB,
  full FT 40GB+. Viable on 96GB, costly.
- *Killed claims:* "SDXL = largest LoRA ecosystem" (0-3), several specific VRAM
  numbers (treat all VRAM figures as approximate), the tidy license-split table.

### Part B — animation (verified)

- **Wan2.2 I2V** is the open fine-tune target. MoE → **two LoRAs** (high-noise +
  low-noise) trained separately (diffusion-pipe / musubi-tuner / AI-Toolkit),
  both applied at inference. Wan2.5/2.6 **not confirmed to exist.**
- **RGBA extraction:** native-alpha research (Wan-Alpha, TransPixeler) is
  LoRA/alpha-token based but **Wan-Alpha is T2V-only — I2V weights unreleased**,
  TransPixeler is T2V on CogVideoX → neither serves I2V today. Practical path:
  **MatAnyone** temporal matting (foreground + per-frame alpha, consistent
  propagation) — needs a first-frame mask (SAM2), but a fixed sprite template
  makes that cheap. The **white/black dual-render diff** trick (banked from
  SpriteDX/exp005) remains the zero-dependency fallback.

### My recommendation (independent reasoning)

1. **The eval harness is the real first move, not model choice.** Since no claim
   benchmarks beauty-vs-NBP or motion-vs-Seedance, committing to a base now is
   guessing. Build the harness (aesthetic + 8-dir consistency + gait scoring),
   then let measured bake-off pick the base. This *is* the repeatable moat.
2. **Start Part A on Illustrious (SDXL-anime); keep Z-Image as the clean-license
   parallel bet.** Jin's read (2026-06-13): Illustrious is the most-recommended
   model so far — which matches the research's proven-aesthetic finding. So start
   there: fastest to a striking result, cheapest LoRA, richest control. Two
   caveats to track: (a) **license per-checkpoint** — Illustrious/derivative
   terms (Fair-AI-public-RAIL etc.) must be checked before shipping commercial
   output; (b) SDXL is an older base with a lower fine-tune ceiling. **Z-Image
   stays the parallel bet** for its clean Apache 2.0 and higher ceiling — and its
   weak ControlNet is moot since template-fill is now optional. Let the eval
   harness decide if Z-Image (or a fine-tune) ever beats the Illustrious result.
3. **Part B: commit to fine-tuning Wan2.2 I2V; treat Seedance-quality as a
   hypothesis to test, not an assumption.** exp005 already shows un-tuned video
   models walk-cycle; the bet is that a style+motion LoRA on our data locks
   fidelity and gait together. Use MatAnyone for alpha now; the white/black trick
   as fallback; revisit Wan-Alpha when I2V weights land.

The honest center: both headline questions (beauty-vs-NBP, motion-vs-Seedance)
are **empirically open** and must be settled on *our* data. The moat is the
apparatus that settles them repeatably.

## Sources

- Wan2.2 fine-tuning tooling: [AMD ROCm Wan2.2 finetune guide](https://rocm.blogs.amd.com/artificial-intelligence/finetuning-wan-part1/README.html), [fal wan-22 trainer](https://fal.ai/models/fal-ai/wan-22-image-trainer), [Medium: training Wan2.2 for character/style](https://medium.com/@ahmadareeb3026/training-wan2-2-for-your-character-custom-style-ultra-realistic-images-f8993350c862)
- Z-Anime: [Civitai Z-Image-Turbo-Anime](https://civitai.com/models/2259646/z-image-turbo-anime), [Next Diffusion guide](https://www.nextdiffusion.ai/tutorials/z-anime-image-generation-in-comfyui), [HF SeeSee21/Z-Anime](https://huggingface.co/SeeSee21/Z-Anime)
- Seedance vs Wan2.2: [Melies comparison](https://melies.co/compare/seedance-v1-pro-vs-wan-v2-2), [WaveSpeed 2026 comparison](https://wavespeed.ai/blog/posts/wan-2-7-vs-seedance-2-vs-sora-2-vs-veo-3-1-fast-image-to-video-comparison/)
- Civitai anime models: [Illustrious / NoobAI / Pony overviews](https://anifusion.ai/models/)
- Local: `experiments/005-walkcycle/notes.md`; SpriteDX repos (paths cited inline).
