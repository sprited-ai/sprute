# Prepare the walking models

The development `animate` command uses SCAIL-2. The older
`animation-models.json` describes WAN Animate and is not the model list for this
command. Use [animation-scail-models.json](animation-scail-models.json).

## Create the server environment

The optional server uses separate projects and model licenses; see the
[component notices](../runtime/THIRD_PARTY.md).

The development installer currently supports **Linux x86_64 with Python 3.12**.
Run it on your NVIDIA GPU server, from a Sprute checkout. Git must be installed:

```sh
python3.12 runtime/prepare-server.py /path/to/new-sprute-server
```

Choose a new folder. The command downloads a pinned ComfyUI checkout and
VideoHelperSuite, creates its own Python environment, installs exact wheel
URLs with SHA256 enforcement, and runs `pip check`. It writes `setup.json`,
`setup.log` and `install-report.json` in that folder. If installation fails,
keep those logs for troubleshooting; the tool refuses an existing folder and
does not currently resume a partial runtime installation.

This installer completed a fresh environment on our existing Linux GPU host in
[experiment 235](../experiments/235-hash-enforced-runtime-install/README.md):
all 104 package versions, wheel URLs and hashes matched the recorded inventory.
[Experiment 236](../experiments/236-installer-eight-direction-walk/README.md)
completed all eight directions in that new environment. All 520 generated RGB
frames and their timing matched the prior run. The 256 transparent output
frames, source provenance, atlas and embedded preview passed mechanical checks.
This reused fully verified model files on the same host; downloading all weights
from scratch and running on another machine remain unverified. These checks do
not establish gait, identity preservation or temporal edge quality.

This does not install a GPU driver, reserve a GPU, or download the model weights.
It is not a Mac or Windows server installer. The resulting CUDA Python packages
still require a compatible host driver. The runtime and weights need substantial
disk space: the tested Python environment alone used about 8.4 GB, in addition
to roughly 26 GB of weights, downloads, caches and outputs.

## Install the models

On the computer running ComfyUI, run this from a Sprute checkout:

```sh
python3 runtime/install-models.py /path/to/ComfyUI/models
```

Replace the path with your actual model folder. This downloads about 26 GB if
none of the models are installed. It verifies every file's size and SHA256,
reuses matching installed files, and refuses to overwrite a different file.
Keep the terminal open until it finishes. If a download fails, run the same
command again: completed files are reused, while the interrupted file downloads
again from the beginning. Temporary files are removed on handled failures;
a force-killed process may leave a hidden `.partial` file, which is never loaded
as a finished model. The destination filesystem must support hard links.

The command installs model weights only. It does not install or start ComfyUI.
Alternatively, download these four files yourself into its `models` folder.
Each link pins an exact publisher revision. Keep the filenames shown:

| Path inside ComfyUI/models | File |
| --- | --- |
| `diffusion_models/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors` | [Download](https://huggingface.co/Comfy-Org/SCAIL-2/resolve/3bd725f20edad6967a65792af3017e251a5bd853/diffusion_models/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors) |
| `text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors` | [Download](https://huggingface.co/Comfy-Org/Wan-Animate-2/resolve/924563469bb8ac056e6171c3123a12903317606d/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors) |
| `vae/wan_2.1_vae.safetensors` | [Download](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/dfcea77bcf258496e20c69cd84e8e8e41909bb3b/split_files/vae/wan_2.1_vae.safetensors) |
| `clip_vision/clip_vision_h.safetensors` | [Download](https://huggingface.co/Comfy-Org/Wan-Animate-2/resolve/924563469bb8ac056e6171c3123a12903317606d/clip_vision/clip_vision_h.safetensors) |

The four files total 25,948,528,468 bytes (25.95 GB) on disk.
That is not a GPU memory requirement. This excludes ComfyUI, its dependencies,
ToonOut, the motion guides and generated outputs.

From a Sprute checkout on that computer, verify the downloaded files:

```sh
python3 runtime/verify-models.py /path/to/ComfyUI/models
```

Replace the path with your actual model folder. This reads every byte and may
take a few minutes. It prints JSON with `"ok": true` only when all four files
match their sizes and SHA256 hashes; exit code 1 means a file failed. Shared
weights linked into the model folder are supported. The tool does not download,
replace or repair files. It needs only Python's standard library.

The runtime used for our completed eight-direction run is ComfyUI commit
`72865f4f27eaf5396f8f36370e0a2be3a9a090ee`, with VideoHelperSuite 1.7.9.
`WanSCAILToVideo` is supplied by that ComfyUI checkout's
`comfy_extras/nodes_scail.py`. The [runtime inventory](animation-runtime.md)
records dependencies and the tested host; its older model table is for WAN.
The [runtime pins](animation-runtime-lock.json) are historical WAN execution
pins, not proof of a clean SCAIL installation on another computer.

## Start and connect

After installing the models into your new server's `ComfyUI/models` folder:

```sh
cd /path/to/new-sprute-server/ComfyUI
../venv/bin/python main.py --listen 127.0.0.1 --port 8188
```

Keep that terminal running. If Sprute runs on a different computer, open a
second terminal there and forward the server port (replace `your-gpu-server`
with your SSH host):

```sh
ssh -N -L 18188:127.0.0.1:8188 your-gpu-server
```

For that forwarded connection use `http://localhost:18188` below; when both
programs run on the same computer use `http://localhost:8188`.

Once ComfyUI is running, check the nodes and model names from your Sprute computer:

```sh
node dist/cli.js check-animation-server --model scail2 --server http://localhost:8188
```

Replace the server address if it is remote. The server check uses model names;
it does not run the full file verifier or prove that the GPU can generate video.
Continue with [step 3 of the walking setup](walking-setup.md#3-make-the-walking-guides)
to prepare motion guides and save your connection.

This is still a development setup. We have completed eight-direction inference
on our existing GPU host. A separate clean code checkout using the independently
installed 083 Python environment also reproduced the front-view video's 65 RGB
frames exactly in [experiment 232](../experiments/232-isolated-scail-runtime/README.md).
That test shares the host and model files; installation and inference on another
machine remain unverified. The manifest identifies exact artifacts, not a completed
third-party license audit or a guarantee of animation quality.
