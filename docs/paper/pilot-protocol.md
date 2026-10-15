# Pilot: direction retention without motion collapse

Version 0.1, 2026-10-14. **Draft specification, not a preregistered or executed study.** Asset selection, runtime verification, and development calibration remain open. Freeze a dated revision before evaluating the held-out characters; record later changes as deviations.

## Question and scope

Does the existing five-frame anchor configuration improve correct-facing animation yield relative to the current CLI API graph, while preserving the requested motion?

Primary hypothesis: the anchored configuration increases the fraction of direction clips that pass both orientation and motion criteria. Report orientation and motion separately as guardrails. A lower flip count with frozen motion is not success.

This pilot evaluates animation from **validated eight-direction inputs**. It does not estimate end-to-end prompt-to-character success, turntable reliability, universal character support, or improvement over other models.

## Stages and budget

| Stage | Design | Purpose |
| --- | --- | --- |
| Setup check | 2 development characters × walk × seed 42 × 2 arms = 4 animation jobs | Verify temporal alignment, decode/export, scoring, actual memory and runtime. Development characters remain outside evaluation. |
| Evaluation pilot | 10 new characters × idle/walk/run × seeds 17/42/101 × 2 arms = 180 animation jobs | 90 paired motion-strip cases, 1,440 direction clips, 30 full character sets per arm. |
| Follow-up | Determined by pilot | Larger held-out set or targeted development ablation; not automatically scheduled. |

Each job produces eight directions jointly. The pilot has **10 independent character clusters**, not 1,440 independent subjects. No power claim is made for this exploratory sample. If 180 jobs exceed the chosen compute budget, amend the design before evaluating outputs; do not stop after favorable results.

Measure median runtime per arm in the setup check. Estimate inference hours as `90 × (median_baseline_seconds + median_anchor_seconds) / 3600`, then separately account for model load, input preparation, export, failures, and review time. Report that a two-character estimate is uncertain. Use available owned compute; new paid capacity requires Jin's approval. No jobs are launched by these documents.

## Character selection and inputs

Select ten original or appropriately licensed humanoid/biped characters, two from each challenge stratum: simple silhouette; asymmetric outfit/accessory; long hair or coat; bulky armor/occlusion; stylized non-human biped proportions. Keep the first pilot within the mannequin driver's plausible domain. This convenience sample does not represent all game art.

Record character ID, source/provenance, permitted research and redistribution uses, reference path/hash, direction-strip path/hash, stratum, and whether it appeared in any prior workflow tuning. Existing tuning characters belong in development only. Do not assume repository availability grants publication rights.

Before either arm runs, inspect all views for identity and expected yaw. Record incorrect or ambiguous views and any correction. A validated or manually corrected strip is eligible for this conditional animation study; preserve the original and count preparation time. Never replace an input because an evaluated animation fails. Track rejected references separately for a future end-to-end study, without combining that rate with this conditional result.

Use the same frozen strip and pre-rendered driver bytes for both arms and every seed. Freeze the GLB hash, mannequin hash, renderer source/version, camera convention, driver dimensions, frame timestamps, and direction order `S, SE, E, NE, N, NW, W, SW`. Visually verify the driver and its first-pose compatibility with the character reference. Do not call the 81-frame window an exact loop without checking its phase.

## Arms and fixed settings

- **B: current CLI graph** — `workflows/sprute-animate-character.api.json`.
- **A: existing anchored graph** — `workflows/alts/sprute-animate-character.anchor.api.json`.

Use isolated graph copies and unique output paths per character/motion/seed/arm/attempt. Do not copy either arm over the production graph. The current CLI does not expose experiment-arm selection; an isolated runner still needs implementation.

Freeze SCAIL-2 FP8 weights, DPO strength 1.0, LightX2V strength 0.8, eight sampling steps, CFG 1, UniPC/simple, shift 5, existing prompts, scale 1.0, 256×256 cells, 768×768 grid, and the same segmentation/export settings. These are the inspected graph settings, not a claim of optimal upstream settings. Record actual weight hashes and runtime dtypes, ComfyUI/custom-node commits, Torch/CUDA, GPU, and deterministic settings. Source repository revisions alone are insufficient.

Schedule paired jobs in a reproducibly randomized order, balancing which arm runs first. Log warm/cold loads, cache hits, and competing GPU workload. Reuse inputs, but do not count cached outputs as fresh inference. A shared numeric seed identifies a paired replication; differing latent lengths mean identical initial noise is not guaranteed.

## Temporal comparability: mandatory setup gate

The baseline requests 81 frames. The anchor graph prepends five driver frames, conditions on five reference-history frames, and removes five decoded frames. Its note reports 80 output frames after the model's frame-length handling. Verify actual behavior on the installed implementation, including WebP frame coalescing and per-frame durations.

Save pre-segmentation RGB, final RGBA, and an explicit generated-frame-to-driver-time mapping. Verify the mapping with driver landmarks before rating motion. If both outputs cover the same first 80 driver samples, use that common interval for the primary orientation/motion comparison. Otherwise determine and document the actual shared interval on development data; stop the evaluation until alignment is resolved. Never score the pinned reference prefix as generated success.

This comparison estimates the effect of the **whole anchor configuration**, including temporal context/length changes. It does not isolate a causal effect of reference history alone. A later prefix-only control and length-matched design are needed for that claim.

Preserve complete untrimmed outputs. Score full exported-loop usability separately and label it descriptive: unequal output durations and non-cycle-aligned windows confound a causal loop comparison. Do not silently crop, interpolate, or select a better cycle for one arm.

## Human review

Two reviewers independently view randomized anonymous clips with the target directional reference and aligned driver. Display at native size and enlarged, on light/dark/checkerboard backgrounds. Show playback plus scrubbing over all generated frames; thumbnails are insufficient. Conceal arm/seed and equalize the primary review interval. If only Jin is available, label results as a single developer's formative assessment and defer independent-review claims.

Record each criterion as `pass`, `fail`, or `uncertain`, plus failure intervals and notes:

| Criterion | Operational rule |
| --- | --- |
| Orientation | Body facing remains consistent with the intended driver view. Wrong-facing intervals totaling at least 250 ms cause failure. Record shorter transients too. Legitimate head turns in the driver are not body-facing errors; separately label head/front-back appearance contradictions. |
| Motion | Requested action is recognizable and follows the driver's timing and major limb movement. An unrequested freeze lasting at least 500 ms during visibly active driving, a different action, or persistent phase failure causes failure. Calibrate idle examples separately so intentional low motion is not penalized. |
| Identity/anatomy | Character features remain recognizable; no persistent extra/missing limbs or major outfit/prop changes requiring redraw. Record subtle defects separately. |
| Alpha/framing | No visible background leakage, cut-off extremities, or foreground loss that prevents use. Judge both raw RGB and RGBA to assign the failing stage. |
| Loop | At normal playback, the exported last-to-first transition is usable without a noticeable pose/position jump. Evaluate full output separately from the primary common interval. |
| Set continuity | Across directions and motions, identity, scale, and ground contact remain compatible for switching states. |

The 250/500 ms thresholds are proposed operational choices, not validated perceptual constants. Calibrate the rubric on development clips, freeze it, and retain interval annotations so sensitivity to thresholds can be reported. Reviewers retain independent labels before adjudication. Report disagreement and uncertain counts. Unresolved uncertainty is non-pass for conservative yield, with a sensitivity analysis counting it as pass.

## Outcomes and analysis

**Primary:** mean, across characters, of the per-character proportion of the 72 direction clips (3 motions × 3 seeds × 8 directions) passing both orientation and motion. Compare A minus B within each character, then report the mean paired difference and all ten character differences.

Report a descriptive 95% character-cluster bootstrap interval by resampling characters with replacement, retaining all their paired arms/motions/seeds/views (10,000 draws, fixed analysis seed). With ten clusters, treat uncertainty as exploratory. Do not bootstrap individual frames or treat directions as independent samples. No post-hoc subgroup significance claims.

Secondary outcomes: orientation failure incidence and duration; motion failure and freeze incidence; identity/alpha criteria; eight-direction motion-strip yield; and complete 24-clip set yield per character/seed. Full-set usability additionally requires loop and set-continuity passes and is descriptive under this pilot's duration mismatch. Report every criterion so strict set yield does not hide partial improvements.

Distinguish execution failures from visual failures. All scheduled cases stay in the operational-yield denominator. Retry only documented transient execution failures with unchanged inputs/settings; retain every attempt and report both first-attempt and eventual yield. Never reroll a visually failed sample. For orientation-specific rates, show completed-case results with missing counts and a conservative all-scheduled yield.

Automated diagnostics may include foreground occupancy, border contact, consecutive-frame difference, apparent motion energy, and loop-boundary difference relative to ordinary transitions. These are flags for review, not standalone quality scores. Static output can score highly on consistency; hair/coat shape makes mannequin silhouette IoU an unreliable correctness target. Do not compute ground-truth PSNR/SSIM against a different-looking mannequin or claim pixel accuracy without matched target frames.

Record end-to-end and stage wall time, peak VRAM, failures/retries, and bytes. Cleanup-time claims require an actual timed editing exercise with the same acceptance criteria; “looks usable” does not measure time saved.

## Decision rules and artifacts

Advance anchoring as a candidate only if primary yield improves without a material motion-loss pattern, and the improvement is not restricted to one character or a favorable seed. Inspect per-character and per-motion tradeoffs before choosing a default. If uncertainty is large, retain both configurations and expand the held-out sample. This pilot does not constitute a statistical non-inferiority test for motion preservation.

For each attempt, persist: run ID/status/error, frozen protocol and source snapshot IDs, character/motion/seed/arm, resolved workflow/hash, input/model/runtime hashes and versions, requested/decoded frames and durations, alignment map, stage timing and memory, output paths/hashes, and retry-parent ID. Store reviewer labels separately with anonymous clip IDs; keep the arm mapping separate until ratings are locked.

Deliver a paired review gallery, machine-readable run/annotation records, per-character results, all failure examples, and a short decision memo. No result values belong in the manuscript until those artifacts exist and have been checked. A subsequent manuscript must distinguish this pilot, later tuning, and a fresh confirmatory evaluation.
