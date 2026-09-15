# Keep an approved direction

Development checkout only; this feature has not been released to npm.

For a provider-backed character build, set `fixedDirections` in your character specification:

```json
{
  "source": "hero.png",
  "states": ["standing"],
  "directions": 8,
  "fixedDirections": {
    "S": "approved/hero-south.png"
  }
}
```

Run `pnpm cli hero.sprute.json` from the repository. This still runs the configured image provider and may use its credits. The provider-backed path is not an offline repair command and does not skip generation for selected cells. The local path skips supplied directions, as described below.

Use a ready-to-use transparent sprite at the intended pixel scale. Paths are relative to the character specification; project defaults resolve from the project directory. Supported keys are N, NE, E, SE, S, SW, W, NW.

After generation, matting, and model review, Sprute replaces each specified cell with your supplied image. Original RGBA pixels are copied without scaling, matting, mirroring or model editing. All final cells use a common canvas sized to the largest selected image, horizontally centered and bottom-aligned with transparent padding. This aligns canvas bottoms, not automatically detected feet. A large reference photograph is therefore not a suitable fixed sprite.

The final spritesheet, turntable and standing preview use these preserved cells. The raw generated sheet and model review images remain raw, and may differ. This does not constrain other generated directions or certify their angles. It is connected to provider-backed and local Node builds, not the browser build API. For the local backend, each supplied image must exactly match `frameSize` by `frameSize`; dimensions are checked before generation. Local builds skip inference and matting for supplied directions.

Missing/unreadable fixed images fail before generation. Cached character builds hash their contents: changing an approved image invalidates the cached result and does not silently resubmit a paid generation. Current cache behavior requires a new output folder for changed inputs.

Pixel preservation is tested through local output packing, including semitransparent colors. The shared paste helper now uses straight-alpha source-over composition; spritesheet packing copies RGBA bytes directly. These fixes prevent color darkening introduced by those assembly steps. They do not repair dark fringes already present in input assets.
