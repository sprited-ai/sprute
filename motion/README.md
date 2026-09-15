# Build local walk templates

This development tool renders one wingless mannequin walking from eight fixed
cameras. It creates motion videos for WAN Animate or SCAIL-2; it does not generate
your character animation or install those models. No image-generation subscription is used.

You need Blender and FFmpeg installed. The renderer was developed with Blender
5.1.2. It currently supports one pinned Quaternius model and action, not arbitrary
GLB files or newer releases of the same library.

From a built development checkout, download the supported template and render
its eight walking guides with one command:

```sh
node dist/cli.js render-animation-drivers --download-template --scail-masks -o my-walk-drivers
```

This uses Blender's included Python to download the 14.5 MB CC0 archive from
Quaternius's OpenGameArt upload, check its exact hash, and render the verified
GLB. The temporary model is removed afterward. You do not need to install a
separate Python for this command. It refuses an existing output folder.
If the upstream archive changes, verification fails before rendering.

If you already have the supported GLB, provide its path instead:

```sh
node dist/cli.js render-animation-drivers walk-template.glb \
  --scail-masks -o my-walk-drivers
```

This command starts Blender with factory settings and embedded scripts disabled.
It finds a standard macOS Blender installation automatically, otherwise uses
`blender` on PATH. Use `--blender /path/to/blender` or `--ffmpeg /path/to/ffmpeg`
for custom installations. Omit `--scail-masks` for RGB-only WAN Animate guides.
The renderer still validates the pinned model and refuses existing output folders.
The development package includes the renderer and its motion license; this command
has not been published in npm 0.4.1.

You can also invoke Blender directly:

```sh
blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python motion/render-walk-drivers.py -- \
  --model '/path/to/AnimationLibrary_Godot_Standard.glb' \
  --output my-walk-drivers
```

For SCAIL-2, add `--scail-masks` to the command. This also renders transparent
source images and creates the eight matching motion-mask videos automatically.

On macOS, Blender may be at `/Applications/Blender.app/Contents/MacOS/Blender`.
Use that full executable path in place of `blender`. If FFmpeg is not on PATH,
add `--ffmpeg /path/to/ffmpeg` after the output argument. Run with factory startup
and disabled embedded script execution as shown. Existing output folders are
never overwritten. A failed run removes its temporary output; it submits no jobs.

The supported archive SHA256 is:

```text
18ff1a7215f4852b320203e8aaf02a1578b5c8eef9027fbaedfcedc7b85a3ac2
```

The script requires this exact extracted GLB SHA256:

```text
1b7bf67866360665426bb99e4c71bd619f19b408453c24e30f0c3071601eee5c
```

The bundled license identifies Quaternius and CC0 1.0 Universal. A copy is retained
in [QUATERNIUS-LICENSE.txt](QUATERNIUS-LICENSE.txt) and each completed bundle.
This is the older DEF-prefixed rig; fixes claimed for later library versions do
not apply automatically. The download helper enforces both hashes. For manual download, use the
[Standard archive](https://opengameart.org/sites/default/files/universal_animation_librarystandard.zip)
from [Quaternius’s upload](https://opengameart.org/content/universal-animation-library)
and locate `Animation Library[Standard]/Godot/AnimationLibrary_Godot_Standard.glb`.

The output contains `bundle.json`, `source-bones.json`, `LICENSE.txt`, and eight
folders named S, SE, E, NE, N, NW, W and SW. Each direction has:

- `frames/`: 32 source PNGs, sampled at 24fps with the duplicate endpoint excluded.
- `first.png`: the exact first source PNG for the paired reference image.
- `driver.mp4`: 65 frames at 24fps, repeating the source cycle twice plus its first frame.

With `--scail-masks`, each direction also contains `mask-source/` with 32 RGBA
source images and `mask.mkv` with 65 lossless FFV1 frames. Pixels with source
alpha at least 128 become blue; all others become black. Motion masks use a black
background, while the character reference identity maps use white. They serve
different inputs in the SCAIL graph.

Experiment [186](../experiments/186-portable-scail-drivers/README.md) rendered
all eight directions with this option. All 256 decoded RGB source frames matched
the earlier renderer, and all 520 decoded mask frames matched both the rendered
alpha threshold and the historical SCAIL masks.
Its separate timing check verified all 16 encoded streams at 65 frames and
24fps, with matching RGB/mask presentation times within 0.501ms rounding tolerance.

All directions use the same action samples with no mirroring. S uses a 30-degree
camera elevation; the other cameras use the previously tested 14.93-degree
configuration. The renderer checks source pose closure, records model/video/image
hashes, and retains source foot/toe/spine coordinates. This does not measure planted
feet or guarantee synchronized or seamless generated character animations.

The source walk has a known nominal-ground limitation: full-mesh audits find
toe/heel points below the near-zero rest-foot plane. A toe-only correction did
not solve the full surface or between-frame clearance. The other bundled formal
walk also retains penetration; see [the comparison](../experiments/194-source-walk-alternative/README.md).
The renderer preserves the pinned original rather than applying an unvalidated
correction. Source pose closure alone is not a foot-contact quality guarantee.

`bundle.json` uses local relative paths. Install its videos and first images and
create the server driver manifest with the development CLI:

```sh
node dist/cli.js upload-animation-drivers my-walk-drivers \
  --server http://127.0.0.1:8188 \
  --server-input /path/on/server/ComfyUI/input -o drivers.json
```

`--server-input` is the actual input directory on the ComfyUI machine, including
any custom input-directory setting. The upload API does not reveal or verify this
absolute path. Give the resulting `drivers.json` to `plan-animation --drivers`.
The command uploads missing files, reads them back and checks hashes; it never
submits a generation job. It reuses identical remote files without overwriting.
If interrupted, rerun the same bundle and output command; the output JSON is only
written after all uploads are verified. An existing output JSON is never replaced.

This has been tested on gin, including server-side file/hash/video checks and
generated workflow paths. The CLI itself checks hashes, PNG dimensions and an
MP4 container header (plus hashes and EBML headers for optional masks); it does not decode videos, validate the supplied server
directory, infer licenses or approve motion. Review newly rendered templates
before use. These tools are checkout-only and not in published npm 0.4.1.
