# ToonOut background removal attribution

Sprute's local background removal uses an ONNX export of ToonOut, a BiRefNet
fine-tune by **Matteo Muratori and Joël Seytre**. The underlying BiRefNet work
is by **Peng Zheng and collaborators**. These are third-party models, separate
from Sprute's code and from the character or animation generation models.

The [ToonOut model card](https://huggingface.co/joelseytre/toonout/blob/cbf720eca394edcde66b861a8a8c20fbabe9c748/README.md)
declares MIT for the model and separately identifies its training dataset as
CC-BY 4.0. Sprute does not bundle that dataset. The included license texts retain
the upstream copyright and permission notices:

- `LICENSE-ToonOut.txt`: [ToonOut code license](https://github.com/MatteoKartoon/BiRefNet/blob/ba5d19a7bf16b1ea7746bb9e9bec83d97dad9709/LICENSE).
- `LICENSE-BiRefNet.txt`: [original BiRefNet code license](https://github.com/ZhengPeng7/BiRefNet/blob/ebcc0bc8ec7fe919cec829f2dea656b3078acddc/LICENSE).

The ONNX conversion is hosted by Sprited at
[sprited/birefnet-toonout-onnx](https://huggingface.co/sprited/birefnet-toonout-onnx/tree/2ded6fe6063fe146b7b30d8b4cfc5636df322525).
The fp16 artifact observed in this project is 492,381,880 bytes, SHA256
`213a8a98ee426ef8f02d247eb5a5a9889359e37c2e1e7e31e282d61034d08a83`.
Model weights download separately; they are not included in the npm package.
The development default downloader pins this revision and verifies downloaded
and cached bytes before loading. Browser callers supplying a custom model URL
remain responsible for identifying that model. Previously published versions
and outputs may predate this verification.

Paper: Matteo Muratori and Joël Seytre, *ToonOut: Fine-tuned Background Removal
for Anime Characters* (2025), [arXiv:2509.06839](https://arxiv.org/abs/2509.06839).

This notice covers ToonOut attribution only. It is not an inventory or license
clearance of the animation server, its encoders, runtime dependencies or assets.
