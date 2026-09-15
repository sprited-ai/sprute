# Experimental local animation runtime

This records the environment observed on gin on2026-09-12. It is a reproducibility
inventory, not a tested other-machine install recipe or a minimum hardware specification.
Published Sprute0.4.1 does not include this animation workflow.

The fixed planner uses four model files under ComfyUI's `models` directory:

| Directory | File | Bytes |
| --- | --- | ---: |
| diffusion_models | wan_animate_2_distill_bf16.safetensors | 32,789,894,104 |
| text_encoders | umt5_xxl_fp8_e4m3fn_scaled.safetensors | 6,735,906,897 |
| vae | wan_2.1_vae.safetensors | 253,815,318 |
| clip_vision | clip_vision_h.safetensors | 1,264,219,396 |

Total model storage is41,043,835,715bytes (about41.04GB), excluding the runtime,
matting model, caches and outputs. This is disk storage, not a VRAM requirement.
[animation-models.json](animation-models.json) records exact SHA256 values,
immutable publisher revisions and download URLs. All four installed files were
fully hashed and matched the publisher's sizes and LFS hashes. The diffusion,
text and vision files are from [Comfy's WAN Animate2 package](https://huggingface.co/Comfy-Org/Wan-Animate-2/tree/924563469bb8ac056e6171c3123a12903317606d);
the VAE is from [Comfy's WAN2.1 package](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/blob/dfcea77bcf258496e20c69cd84e8e8e41909bb3b/split_files/vae/wan_2.1_vae.safetensors).

The runtime snapshot in [experiment073](../experiments/073-runtime-inventory/observed.json)
records:

- ComfyUI0.33.1 at commit72865f4f27eaf5396f8f36370e0a2be3a9a090ee.
  Its only reported tracked change is deletion of a checkpoint placeholder file.
  WanAnimate2ToVideo is supplied by `comfy_extras/nodes_wan.py` in this checkout.
- VideoHelperSuite1.7.9, installed as a package with no independent Git checkout.
  The snapshot records hashes for45 package-listed files. Its Git commit is
  unknown; using `git -C` without checking the repository root would incorrectly
  report the parent ComfyUI commit. Experiment074 matched all45 files against the
  official1.7.9 registry archive. [animation-runtime-lock.json](animation-runtime-lock.json)
  now pins that archive URL and SHA256 as well as the ComfyUI commit.
- Python3.12.13; torch2.11.0+cu128; torchvision0.26.0+cu128;
  torchaudio2.11.0+cu128; numpy2.5.0; safetensors0.7.0;
  transformers5.9.0; aiohttp3.13.5; av18.0.0; FFmpeg6.1.

ComfyUI and VideoHelperSuite each contain a GPLv3 license text; keep their source
and notices distinct from Sprute's MIT code. Publisher model-repository labels
are Apache2.0, but this is not a completed upstream encoder, matting or transitive
notice audit. No third-party runtime or weights have been bundled for release.
See [provenance notes](animation-provenance.md).

A fresh one-element PyTorch CUDA allocation and addition succeeded on the RTX PRO
6000 Blackwell Workstation Edition, reporting101,973,491,712bytes total device
memory. This tiny operation does not establish full WAN capacity or a minimum GPU.
At the same time, `nvidia-smi` failed because installed NVML595.91 differs from the
loaded kernel driver595.84. Do not treat this mixed host state as a clean driver
setup. No driver update or reboot was performed during this audit.

Experiments074/075 completed a fresh dependency installation, pip check, isolated
server startup and one65-frame WAN front-view generation (91.21seconds). All65
frames were inspected in contact sheets; motion quality remains unapproved.
The new runtime shares the same host and verified model files. Next reproduction
work: validate another machine and measure peak memory. Experiment083 directly installed
the derived104-package list into another fresh venv on the same host: pip check
passed and all104 package versions/download URLs/artifact hashes matched the
recorded inventory. This is post-install verification, not enforced hash locking;
083 inference remains untested. `check-animation-server` remains
a node/input/model-name check; it does not verify these file hashes or host health.

Experiment084 validated the exact wheel URL/hash requirements with pip's
`--dry-run --ignore-installed --require-hashes --no-index --only-binary=:all:`.
All104 resolved versions, URLs and SHA256 hashes match the inventory. The file
`runtime/requirements-linux-cu128-hashed.txt` targets Linux x86_64/CPython3.12.
This was a dry run on the same host, not a fresh hash-enforced installation or
another inference test.
