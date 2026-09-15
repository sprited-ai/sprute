# Sprute image-edit model survey — 2026-09-14

Pixel / @pix-el. Scope: publicly available instruction-based image editing models relevant to local character-preserving, four-at-a-time direction generation. This is a primary-source survey, not a cross-model performance benchmark. Includes 2025 foundations still relevant in 2026. No new model weights downloaded or paid inference requested for this survey.

## Decision

Broaden beyond Qwen. First practical comparison: FLUX.2 klein 4B, LongCat Image Edit Turbo, and current Qwen2511 control. Add HiDream O1 full for explicit layout/skeleton conditioning; then SenseNova U1.5 and LLaDA Image Turbo after memory/runtime preflight. A published editing benchmark does not prove correct chibi compass views.

The final output remains a symmetric 3×3 compass sheet: NW/N/NE; W/source/E; SW/S/SE. At most four new views per call. Preserve accepted images and generate remaining subsets without mirroring asymmetric details. Multi-reference input support is not the same as jointly generating four or eight correct views.

## Models and evidence

| Candidate | Official capabilities / release evidence | Local memory evidence | License and Sprute implication |
|---|---|---|---|
| FLUX.2 klein 4B | Unified generation/editing; native multi-reference; distilled example uses four steps | Vendor states approximately 13GB VRAM; not a measurement of our grid | Apache-2.0. First practical candidate. [Model](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) |
| FLUX.2 klein 9B / base / KV variants | Multi-reference editing; family includes higher-capacity and KV-cache variants | Must measure chosen checkpoint and reference count; do not reuse 4B memory figures | 9B non-commercial license differs from 4B Apache. Research comparison, not automatic default. [Repository](https://github.com/black-forest-labs/flux2) |
| LongCat Image Edit / Edit Turbo | Instruction editing and content preservation; Turbo uses eight NFEs | Official Turbo example states approximately 18GB with model CPU offload | Edit model card Apache-2.0. Good lightweight independent comparison. Single-image path demonstrated; native multi-image API not established here. [Edit](https://huggingface.co/meituan-longcat/LongCat-Image-Edit), [Turbo](https://huggingface.co/meituan-longcat/LongCat-Image-Edit-Turbo) |
| HiDream O1 Image full | Released May 8, 2026; unified editing and subject personalization; explicit multi-reference, skeleton and bounding-box layout examples | No directly verified 32GB recipe in sources reviewed. Full checkpoint inventory and peak memory need inspection | MIT. Particularly relevant to our layout failure. Authors recommend full for editing; do not substitute Dev-2604 text-to-image ranking. [Model and usage](https://huggingface.co/HiDream-ai/HiDream-O1-Image) |
| SenseNova U1.5 8B MoT | Current released model supports multi-reference edits, visual markers and bounding boxes; describes preserving identity and unedited content | HF reports 18B total stored parameters despite 8B model name. BF16 weights alone imply roughly 36GB decimal before overhead; 32GB needs quantization/offload investigation | Apache-2.0. Strong capability match, but exact layout and complex-edit drift remain explicit limitations. [Model](https://huggingface.co/sensenova/SenseNova-U1.5-8B-MoT) |
| LLaDA Image / Turbo | Released September 4, 2026; six-billion-parameter generation/editing family; Base50/Turbo4 steps; official BF16 and FP8 checkpoints | Whole pipeline includes additional components; six-billion headline is not a VRAM guarantee. No measured 32GB recipe established here | Model card Apache-2.0. Latest lightweight candidate. Official editing example has one reference. Training code still listed coming soon. [Repo](https://github.com/inclusionAI/LLaDA-Image), [Model](https://huggingface.co/inclusionAI/LLaDA-Image) |
| FireRed Image Edit 1.1 / 1.0 Distilled | 1.1 released March3; improves consistency and fusion. Separate optimized inference path announced March1 | Repo reports 30GB and approximately4.5s/sample for optimized path, not our hardware/task or necessarily default1.1 | Apache-2.0 code/weights. Near memory ceiling; benchmark after smaller candidates. [Official repo](https://github.com/FireRedTeam/FireRed-Image-Edit) |
| UniPic3 | January9 release; Qwen-Image-Edit-based multi-image composition;1–6 inputs;8-step distillation | Not an independent low-memory backbone; no verified32GB recipe here | Repo MIT; inspect selected weights and base terms. Useful alternative training recipe, not independent evidence against Qwen architecture. [README](https://raw.githubusercontent.com/SkyworkAI/UniPic/main/UniPic-3/README.md), [project](https://github.com/SkyworkAI/UniPic) |
| DyRef | July2 code/data/weights release; improves multi-reference conditioning through SFT/RL; Qwen2511 LoRA quickstart; experiments include klein-base9B | Adapter does not eliminate base memory requirements | Repo Apache-2.0; base checkpoint license still applies. Potential adapter route after baselines. Author-reported benchmark parity with Nano Banana Pro is task-specific. [Repo](https://github.com/Weistrass/DyRef) |
| Step1X Edit v1.2 | Instruction reasoning and reflection; published local v1.2 inference implementation | Needs its specific Diffusers branch and memory preflight; no32GB proof gathered | Keep as secondary reasoning-oriented comparator; verify exact checkpoint license before integration. [Repo](https://github.com/stepfun-ai/Step1X-Edit) |
| OmniGen2 | 2025 foundation, still relevant; instruction editing and in-context multi-image generation | Official approximately17GB native; offload available; slower sequential offload reduces further | Repo Apache-2.0. Useful independent baseline, behind newer candidates in test priority rather than proven quality. [Repo](https://github.com/VectorSpaceLab/OmniGen2) |
| BAGEL | Unified understanding/generation, editing and multiview research capability | No physical32GB result verified here; quantization/runtime investigation required | Repo Apache-2.0. Research baseline; multiview examples are not an eight-direction sprite guarantee. [Repo](https://github.com/ByteDance-Seed/Bagel) |
| HunyuanImage3.0 Instruct / Distil | January26,2026 release; instruction reasoning, editing, multi-image fusion; Distil recommends8steps |80B total/13B active; official Instruct recommendation at review time is at least8×80GB. Distillation reduces steps, not necessarily weight size | Separate Tencent license review needed. Large-compute comparison, not first32GB default. [Official README](https://github.com/Tencent-Hunyuan/HunyuanImage-3.0/blob/main/README.md) |
| Z-Image Edit / Omni-Base | Listed as models, but official Model Zoo still marks weights “To be released” | No installable official editing checkpoint verified | Exclude from immediate run queue. Turbo's8steps/16GB claims concern generation model, not Edit. [Official model zoo](https://github.com/Tongyi-MAI/Z-Image#-model-zoo) |

All memory figures above are vendor/runtime documentation, except the explicitly labeled arithmetic estimate. They are not measured Sprute results. Hardware, precision, resolution, reference count, CPU offload, warmup and CFG alter both memory and latency. Do not convert model names or parameter counts into exact download totals.

## Sprite-specific LoRA finding

The [fal klein4B spritesheet LoRA](https://huggingface.co/fal/flux-2-klein-4b-spritesheet-lora) is real and has downloadable fal/Comfy files. However it was trained on48 selected vehicle/object pairs and produces a fixed2×2 layout: two isometric views, one left profile, one bird's-eye view. Its example targets the **base** editing endpoint. It is not a cardinal-four character model; bird's-eye is not rear-N. Keep as a training/layout precedent or separate experiment, not a drop-in Sprute solution or a4-step distilled recipe.

## What existing evidence says

Qwen2511 experiment403 produced recognizable individual left-profile and rear candidates. Joint404 produced direction duplicates and missing sneakers. Compass405 produced four broad views but violated placement, erased center and crossed boundaries. These failures are specific to these recipes, not proof that every Qwen approach fails. Masked406 is a separate experiment; no quality claim is made by this survey.

Photographic portrait benchmarks do not measure pixel-art palette, discrete camera yaw, asymmetrical equipment, feet alignment, or temporal loopability. We should choose a model using accepted-view yield and total retry cost rather than general preference rank or vendor “SOTA” wording.

## Nine-case first comparison (proposed, not run)

Use three sources: current Lily; a chibi character with a deliberately asymmetric accessory; a nonhuman or substantially different silhouette. For each source run:

1. Four cardinal views together, same3×3 compass target.
2. One correct rear view from original, testing unseen clothing/hair geometry.
3. Two diagonals using original plus visually accepted adjacent cardinals where the model supports native multi-reference. For single-reference models use a clearly labeled composite and record that conditioning differs.

Three sources×three tasks=9cases per model. Match source assets, requested views and output pixel budget; use each model's documented sampler and separately report steps/NFEs. Start with one fixed seed as a smoke test; only promising models proceed to multiple seeds. Do not compare cherry-picked outputs.

Score actual character facing (not camera-label wording), body completeness, identity/clothes/accessories, cell placement, common scale/foot baseline, duplicate views, and pixel-art preservation. Report every requested slot, even failed ones. Record cold load time, warm generation time, total retry time, precision/offload, weight bytes, allocator peak, and device-wide memory where available. Our96GBgin GPU with a28GiB allocator cap is not proof of physical32GB compatibility.

No candidate enters the animation stage until the directional reference set passes visual review. After a candidate wins, evaluate temporal consistency and reusable idle/walk/run cycles separately. Static editing support alone does not implement the full Sprute vision.
