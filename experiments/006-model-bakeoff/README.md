# 006 — model bake-off (the moat's measurement apparatus)

Pick the base model with **measurement, not vibes** (docs/007). Same prompt set,
every candidate, scored by a VLM judge on the pretty-vs-stale axes. Repeatable:
re-run as new models/LoRAs land and the ranking stays comparable.

## Why this exists

The deep-research found that *nothing benchmarks open-model anime aesthetics vs
Nano Banana Pro* — every claim is a vendor card or blog. So we settle it on our
own data. This harness is that settle: it turns "which looks best" into a number.

## What to compare — full pipelines, not bare base outputs

The pretty-vs-stale gap is mostly the *pipeline*, not the base
(docs/007 playbook). So each candidate is **base + refinement**, run on
gin + ComfyUI:

| candidate | base | notes |
|---|---|---|
| `zanime/` | Z-Anime (Z-Image) | the moat lead — Apache 2.0, high fine-tune ceiling |
| `illustrious/` | Illustrious XL (+ a derivative) | proven-aesthetic benchmark to beat |
| `noobai/` | NoobAI-XL (v-pred) | second SDXL-anime reference |
| `nbp/` | Nano Banana Pro | the baseline we're trying to beat |

Refinement to apply per SDXL-anime candidate (so the comparison is fair):
native-dialect prompt → hires fix → FaceDetailer → low-denoise tiled upscale.
Z-Anime uses its own native prompting (the SDXL tag dialect may not transfer —
that's part of what we're testing).

## Prompt set

Fix ~8–12 character prompts spanning the range we care about (full-body single
character, varied archetypes), e.g.:

```
a small forest fairy with green wings
a goblin archer with a rusty crossbow
a stoic knight in ornate silver armor
a cheerful tavern cook with a big ladle
a wandering swordswoman with a straw hat
a tiny robot with a single glowing eye
an elderly wizard with a star-patterned robe
a punk catgirl with headphones
```

Same prompts, same seed list, every candidate. Drop each model's outputs in its
subfolder (one PNG per prompt; single full-body character renders, not sheets).

## Score

```sh
GEMINI_API_KEY=... npx tsx experiments/006-model-bakeoff/score.mts ./bakeoff
```

`gemini-2.5-flash` (the judge sprute already uses for QC) scores each image 1–10
on **aesthetic / illustration / anatomy / detail / appeal**, plus a
`striking|solid|generic` verdict and a note. Output: per-image table + per-model
mean ranking. Subdirectories = one model each.

Validated: the judge discriminates — on a smoke test it scored a crafted
character "solid" and correctly flagged a plain photo as "generic" for this rubric.

## Reading it

- **Per-model mean** picks the base to commit fine-tune budget to.
- **Beat NBP** is the bar: the chosen open pipeline's mean must clear the `nbp/`
  baseline on `aesthetic`/`appeal`, or the move off NBP isn't justified yet.
- The VLM judge is a *proxy*. For the final call, also eyeball the top/bottom
  images — and consider a human poll (Jin) on the shortlist.

## Caveats

- One judge model, one rubric → consistent but not ground truth. Vary the rubric
  or add a second judge if results look off.
- Keep the image set and seeds fixed across runs or the ranking isn't comparable.
- This scores *single-image aesthetics*. 8-direction consistency and animation
  gait need their own metrics (next harness; see docs/007 experiments list).
