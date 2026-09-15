# Animation provenance and distribution notes

Update 2026-09-14: [ToonOut attribution](../third-party/toonout/README.md) now
includes the upstream author notices, pinned model/code sources and original
MIT license texts. Those notice files are included in the package file list.
Experiment 237 records the source snapshots and pack check. This resolves that
specific attribution omission, not the full runtime/encoder/license inventory
described below. Development update 238 pins the default ToonOut download to
an immutable revision and verifies size/SHA256 in Node and browser paths.
The published package and running experiment 236 still use the older build.

Checked 2026-09-12. This is a record of verified sources and remaining release work,
not a completed clearance of every dependency or asset.

| Component | Evidence | Current distribution decision |
| --- | --- | --- |
| Sprute code | Repository `LICENSE`: MIT, Sprited 2026 | Keep the existing license notice with source/package distribution. |
| WAN Animate 2 code | [Official license](https://github.com/Wan-Video/Wan-Animate-2/blob/main/LICENSE): Apache-2.0 | Record independently from Sprute's MIT license; do not relabel third-party code as Sprute code. |
| WAN Animate 2 weights | [Official model card](https://huggingface.co/Wan-AI/Wan2.2-Animate-2-14B): Apache-2.0 | Link to upstream downloads; no weights are bundled by this work. |
| Comfy repack of distilled weights | [Comfy model card](https://huggingface.co/Comfy-Org/Wan-Animate-2) identifies the upstream model and Apache-2.0 | Verify the installed bytes against the published artifact, not only the filename. |
| Comfy runtime, custom nodes, text/vision encoders, VAE, matting | Separate components used by the workflow | Their versions, notices and individual license scopes still need a complete inventory before a bundled runtime release. |
| Seedance-generated Lily motion clips | Generated using a paid partner node; see experiments 013 and 017 | Treat as experimental references. The exact provider terms applicable to redistribution of these clips are not yet established here. Do not infer an open asset license from Sprute's code license. |
| Character sheets and other templates | Existing project assets used in experiments | Record creation/source and intended asset license individually before shipping a reusable template pack. |

Comfy's [terms](https://comfy.org/terms-of-service), effective May 13, 2026,
retain customer rights in inputs/outputs as between Comfy and the customer, while
also making partner-node use subject to the applicable provider's terms. They
separately exclude Comfy OSS from those commercial-product terms. Those statements
alone do not settle the Seedance provider terms or an asset's copyright status.
This does not say that template redistribution is prohibited; it is unverified.

Keep optional proprietary template creation clearly identified. A reproducible
local workflow can accept a user's own licensed motion video, but Sprute still
needs a tested local reference route and a reusable, explicitly licensed template
set to meet the project's full objective.

## Configuration findings affecting the next experiment

The [official model card](https://huggingface.co/Wan-AI/Wan2.2-Animate-2-14B)
shows a distilled Diffusers example with Euler, 10 inference steps and guidance
1.0. It also recommends an appearance/background caption format in Chinese,
without describing action. Our experiments used UniPC, six steps, English
appearance-plus-motion prompts and a sampling shift of 8.

The [upstream YAML](https://github.com/Wan-Video/Wan-Animate-2/blob/main/infer/wan_animate_2_distillation.yaml)
contains Euler, shift 5 and defaults that differ from the README invocation
(including step/guidance values). Therefore copying one number is not evidence
of reproducing the upstream pipeline. Pin both implementation and invocation.
First compare Euler/10 against the existing baseline with every other input
fixed; inspect the whole failed rear clip, then test caption format separately.
Do not claim that either change will fix the artifacts before measuring it.

The upstream project also reports text-driven viewpoint control. This is worth
testing with one shared driver for different target facings, but it is not proof
that our installed Comfy path supports reliable eight-direction sprite control.
No new model download or generation was performed for this source audit.

## Current inventory update

Experiment073 verified full installed bytes for all four planner model files
against immutable publisher LFS metadata. animation-models.json now includes
the text encoder, VAE and vision encoder as well as the diffusion checkpoint.
[Runtime inventory](animation-runtime.md) records ComfyUI0.33.1, package-based
VideoHelperSuite1.7.9 and observed Python dependencies. Both runtime projects
contain GPLv3 license texts, separately from Sprute MIT and model-repository
Apache2 labels. Upstream auxiliary attribution and transitive/matting notices
remain incomplete. The local CC0 Quaternius motion route is now rendered and
installed through070/071; older Seedance provenance remains separate.
