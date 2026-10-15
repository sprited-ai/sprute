# Sprute research direction

Date: 2026-10-14. Status: initial research specification; no new GPU experiments or human study conducted.

## Decision

Investigate **direction retention versus motion fidelity in complete multi-directional sprite animation sets**. Start with the existing first-frame anchoring variant. Use the results to decide whether the next engineering priority is conditioning, reference generation, motion transfer, or export quality.

Working paper title: *Evaluating Directional Reliability in Generative Sprite Animation*. Keep the broader title, *Sprute: A Reproducible Pipeline and Evaluation for Multi-Directional Character Animation*, as an alternative if the system evaluation becomes the main contribution.

This is a plausible research direction, not an established novel method. A useful outcome would be a reproducible failure analysis and an intervention that improves usable animation yield without suppressing motion. A release description alone is insufficient.

## Read next

- [Manuscript draft](sprute-paper.tex): English LaTeX draft with system description, related work, evaluation design, and explicitly unmeasured results. Open in the built-in LaTeX editor for the PDF preview.
- [Prior-work comparison](prior-work.md): what existing work covers, what we can reasonably investigate, and what remains unverified.
- [Pilot protocol](pilot-protocol.md): staged experiment, controls, scoring, analysis, and decisions.
- [Source snapshot](source-snapshot.json): exact source hashes and declared settings at the time of this review. This is not a runtime or model-weight audit.

## What the current checkout establishes

The inspected CLI calls API graphs. Character generation, turntable generation, motion rendering, animation, and export are distinct stages. These observations concern source behavior; this review did not reproduce inference.

| Stage | Observed implementation | Research implication |
| --- | --- | --- |
| References | AniSora turntable; reverse frames; sample indices 0,10,…,70 into eight views | Equal time spacing does not prove equal yaw spacing. Validate view labels before attributing errors to animation. |
| Driver | GLB retargeted/rendered on Template-kun; eight camera directions; default 81 frames at 24 fps | Driver orientation and pose alignment are testable inputs. A looped motion does not ensure the exported window spans an exact cycle. |
| Animation | Eight views occupy a 3×3 grid with an empty center; SCAIL-2 FP8 graph, DPO and LightX2V LoRAs | Joint spatial conditioning is already implemented, but benefits over independent views have not been established here. |
| Export | Decode, restore size, split cells, BiRefNet ToonOut, concatenate into a strip | Separate generative defects from segmentation/export defects by retaining pre-removal RGB. |
| Anchoring variant | Five copies of the first driver frame; five reference history frames; remove five output frames | Compare a package of changes first. Do not attribute every difference solely to anchoring. |
| Reproducibility | Pinned model repository revisions and custom-node revisions; content-addressed input names and saved workflow metadata | Useful foundation. Actual installed versions, model hashes, hardware, and output provenance still need capture. |

Evidence: `src/sprute/{generate,turntable,motion,animate,models,setup,comfy}.py`, `custom_nodes/sprute/{layout,renderer,__init__}.py`, and the API graphs listed in the snapshot.

The UI graph `workflows/sprute-animate-character.json` had pre-existing uncommitted edits during review. The CLI loads `workflows/sprute-animate-character.api.json`; the two must not be treated as interchangeable experimental configurations. Concurrent edits to `custom_nodes/sprute/{layout,__init__}.py` also appeared during review, adding square-cell padding. The snapshot captures the later working-tree files, not just HEAD; freeze the chosen version before execution. The proposed square 256×256 cells are unaffected by that padding change. No production source or graph was changed by this research task.

## Existing evidence and its limits

`workflows/alts/sprute-animate-character.anchor.md` reports an October 11 comparison of 21 runs: 10 flips in the current workflow and 3 with anchoring, mean relative motion energy 0.92, and one idle example at 0.40. This is a **historical note**, not a result independently reproduced in this review. Raw run manifests, scoring definitions, paired outcomes, and artifacts were not recovered here. Do not derive significance or a publication headline from these counts.

`workflows/alts/sprute-animate-native-parity.md` documents one native/Comfy comparison and explicitly warns about precision, initial noise, sampling, and timing differences. It cannot establish a backend speed advantage or general directional reliability.

## What would make the paper valuable

1. A documented task and evaluation of the whole eight-direction, three-motion set, including failed runs and unusable directions.
2. A controlled finding about the orientation–motion tradeoff, tested on characters excluded from workflow development.
3. Reusable inputs, configuration manifests, outputs where redistribution is permitted, and scoring instructions.
4. Honest attribution to the upstream models and a clear account of what Sprute adds.

The first pilot only compares two Sprute configurations. It cannot establish superiority to other methods. A paper claiming wider superiority needs compatible external baselines and a larger, separately held-out evaluation. A negative pilot can still guide the product, but is not automatically a publishable contribution.

## Decisions the results should drive

| Observation | Next engineering work |
| --- | --- |
| Anchoring improves facing and preserves motion across characters | Harden the variant, then test prefix length and phase alignment on separate development data. |
| Facing improves but motion freezes or starts late | Investigate reference/driver pose mismatch, prefix duration, and history conditioning. Do not promote based on flip counts alone. |
| Correct input views still turn into the wrong views | Test view-specific conditioning and independent-view generation. |
| Most failures already exist in the direction strip | Prioritize turntable yaw validation and reference construction. |
| Raw RGB is sound but alpha/edges fail | Prioritize segmentation and export. |
| Both arms retain facing but exported loops jump | Prioritize cycle boundaries and temporal export; more orientation work is unlikely to help. |
| Results differ substantially between characters or remain inconclusive | Expand the character sample after revising the hypothesis; report uncertainty rather than selecting favorable seeds. |

Immediate implementation order: recover historical artifacts if available; select and document two development characters; build an isolated runner and review exporter; run the four-job setup check in the protocol; freeze ten evaluation characters and the rubric; then execute the pilot. Do not overwrite the production API graph to switch experiment arms.
