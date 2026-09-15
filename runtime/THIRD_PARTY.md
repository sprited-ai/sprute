# Animation server sources and notices

Sprute's code is MIT-licensed. The optional server installer downloads separate
projects with their own notices. It does not change their licenses or bundle
their code into the npm package.

| Component | Observed source notice | Where it is retained |
| --- | --- | --- |
| ComfyUI, commit `72865f4f27eaf5396f8f36370e0a2be3a9a090ee` | [GPLv3 license text](https://github.com/Comfy-Org/ComfyUI/blob/72865f4f27eaf5396f8f36370e0a2be3a9a090ee/LICENSE) | Installed `ComfyUI/LICENSE` and full source checkout |
| VideoHelperSuite 1.7.9 | GPLv3 license text in the pinned registry archive | Installed `ComfyUI/custom_nodes/comfyui-videohelpersuite/LICENSE` and package sources |
| SCAIL-2 fp8-scaled checkpoint | MIT declared in the [pinned Comfy model card](https://huggingface.co/Comfy-Org/SCAIL-2/blob/3bd725f20edad6967a65792af3017e251a5bd853/README.md) and [official model card](https://huggingface.co/zai-org/SCAIL-2/blob/150cc0ca4e98e50e60b9295dacde39442fdccab2/README.md) | Model files download separately; card sources and hashes are recorded in the model manifest/audit |
| Official SCAIL-2 training/inference repository | [Apache-2.0 code license](https://github.com/zai-org/SCAIL-2/blob/wan-scail2/LICENSE) | Reference source; this installer uses ComfyUI's implementation, not this repository |
| ToonOut background remover | [Separate model and author notices](../third-party/toonout/README.md) | Included in the Sprute package's `third-party/toonout/` folder |
| Quaternius motion source | CC0-1.0 | `motion/QUATERNIUS-LICENSE.txt` and generated motion bundles |

Do not describe the SCAIL code repository's Apache license as the model card's
license, or describe the entire installed server as Sprute's MIT code.

This is a component source record, not a complete redistribution checklist.
The UMT5/CLIP/VAE upstream chains and the 104 Python packages (including NVIDIA
runtime components) still need a complete notice inventory before distributing
a bundled server image. `prepare-server.py` installs those packages separately
from pinned wheel URLs and preserves the packages' installed metadata. Generated
characters and other assets have separate provenance; these software notices
do not assign them an asset license.
