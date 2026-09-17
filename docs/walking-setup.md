# Set up walking

**Experimental workflow in Sprute 1.0.** These instructions use a source checkout
to prepare the GPU server and motion guides. The npm package includes `animate`,
but does not provision the server or install its model weights.
If you only want standing character pictures, use the [character guide](../README.md#make-a-character).

There are two parts: Sprute runs on your computer, and a GPU server makes the
animation videos. They can be on the same computer. If you do not have a GPU
server, you will need help with that part before continuing. Sprute does not
rent one for you. A Replicate key for character pictures does not connect an
animation server.

## 1. Prepare Sprute on your computer

Open a terminal in the Sprute source folder, the folder containing
`package.json`. You need Node.js, pnpm, Blender, and FFmpeg with ffprobe installed.
The tested setup uses Node.js 22, Blender 5.1.2 and FFmpeg 8.0.1; this is not a
claim that every version or operating system has been tested.

Build the development commands:

```sh
pnpm install --frozen-lockfile
pnpm build
node dist/cli.js animate --help
```

The last command should explain how to make a character walk. If it says the
file is missing, check that the build finished and you are in the Sprute folder.
Keep using this folder for the remaining commands.

Check the video tools:

```sh
ffmpeg -version
ffprobe -version
```

Both should print a version. The background remover also needs
`onnxruntime-node`, an optional package installed with Sprute. Before a new
generation starts, Sprute checks these local tools and loads the background
remover. Its first use downloads the roughly 492 MB ToonOut model.

## 2. Connect your GPU server

The server needs ComfyUI with SCAIL-2, based on Wan2.1 14B. Follow the
[server setup](animation-scail-setup.md) on the GPU computer to install the
runtime and four model files, verify them, and start the server. The installer
currently supports Linux x86_64 with Python 3.12 and a compatible NVIDIA driver.

Keep two details from that setup:

| Detail | Example |
| --- | --- |
| Server address, as reached from your Sprute computer | `http://localhost:8188` |
| Full input folder on the GPU computer | `/home/you/sprute-server/ComfyUI/input` |

If the server is on another computer, follow the SSH forwarding step in the
server guide and keep that terminal open. With its example forwarding command,
the address on your Sprute computer is `http://localhost:18188`. Use that address
in **all three commands below** that take `--server`.

Check the connection from your Sprute folder:

```sh
node dist/cli.js check-animation-server --model scail2 --server http://localhost:8188
```

Resolve any reported missing nodes or model names before continuing. This
checks the server's interface; the separate server-side model verifier checks
the actual model files. Neither check proves enough GPU memory for generation.

## 3. Make the walking guides

A walking guide is a video of a mannequin showing the movement to copy.
Create all eight guides once:

```sh
node dist/cli.js render-animation-drivers --download-template --scail-masks -o my-walk-drivers
```

This downloads the supported Quaternius CC0 template, verifies it, and runs
Blender to render the guides. It needs no image-generation API key. Keep
`--scail-masks`: SCAIL-2 needs those extra guide files. Wait for it to finish.
The result is a new `my-walk-drivers` folder with eight direction folders and
`bundle.json`.

If Blender cannot be found, add `--blender /full/path/to/blender` to the command.
Sprute finds the standard Blender app on macOS automatically. See the
[motion guide details](../motion/README.md) for custom paths or an existing GLB.
The renderer refuses an existing output folder; use a new name for a new render.

## 4. Send the guides and save your connection

Replace the example `--server-input` path below with the actual input folder
from step 2. This is a folder on the **GPU computer**, even when you run Sprute
on a different computer:

```sh
node dist/cli.js upload-animation-drivers my-walk-drivers \
  --server http://localhost:8188 \
  --server-input /home/you/sprute-server/ComfyUI/input \
  -o drivers.json
```

The uploader sends the files and verifies their bytes. It cannot discover or
validate that absolute input-folder setting for you. If the upload is
interrupted, repeat the same command; verified remote files are reused. Once
`drivers.json` has been written successfully, continue:

```sh
node dist/cli.js animate setup --drivers drivers.json --server http://localhost:8188
```

You should see `Saved` followed by the path to `sprute.animation.json`. These
steps submit no animation jobs. Keep `drivers.json` and the saved settings in
place, and run your animations from this same Sprute folder. Leave the GPU
server and any SSH forwarding terminal running.

## 5. Make your first walk

Use your character's eight-view `.spritesheet.png`:

```sh
node dist/cli.js animate outputs/my-character.spritesheet.png --wait
```

Replace `my-character` with the actual filename. This step starts the eight
generation jobs. Open the `preview.html` path printed when the command finishes.
The [walking guide](walking.md) explains what to inspect, how to continue an
interrupted run, and how to try the result in Godot.

You only repeat step 5 for your next character while using the same server and
saved setup. Changing servers also requires installing the guides there and
updating your connection.

## If setup stops

| Message or symptom | What to check |
| --- | --- |
| Cannot reach the animation server | Keep ComfyUI and any SSH forwarding terminal open; check the address and port. |
| Missing SCAIL nodes or model names | Follow the SCAIL-2 server guide; the older WAN Animate model list is different. |
| Output already exists | Keep the completed output, or choose a new output name. Do not overwrite an animation to resume it. |
| Settings already exist | Your connection is already saved. Inspect `sprute.animation.json` before changing it. |
| ToonOut cache mismatch | Sprute leaves the file unchanged. Inspect the named file; remove only that file if you want to download the pinned model again. |

The model download checks its exact size and SHA256 before loading. A handled
failed download is not saved as a completed model. Server setup, correct files
and successful generation still do not guarantee a clean animation: character
details, feet, thin edges and the loop transition need visual review.
