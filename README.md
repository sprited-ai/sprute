# sprute

Open workflow for generating **8-direction game character sprites** from a
single reference image, using template-guided image models (Nano Banana Pro
and friends).

Made by [Sprited](https://spritedx.com) — this is the workflow behind the
character sheets we've been posting. People kept asking "mind sharing your
workflow?" — this repo is the answer.

![turnaround](https://raw.githubusercontent.com/sprited-ai/sprute/main/examples/monet.turntable.webp)

## The technique

1. **Example-anchored template.** A labeled sheet: top row shows a worked
   example (reference photo → 5 direction sprites), bottom row has your
   reference + empty slots. The model completes the pattern. No fine-tuning,
   no LoRA — one image-edit call.
2. **5 directions, not 8.** Generate S, SE, E, NE, N; mirror SE/E/NE into
   SW/W/NW. Halves the consistency burden. (Caveat: asymmetric details flip.)
3. **Harvest.** Auto-detect the sprite panel, slice cells, remove the
   background with a dependency-light floodfill keyer (no GPU matting needed
   on flat template backgrounds), assemble animated WebP turnarounds.

We use Nano Banana Pro (`google/nano-banana-pro`, via Replicate) — currently
the only model that reliably does both reference-fill and new-character
creation while preserving the template layout. Seedream 4.0 / Qwen-Image-Edit
comparisons (partial successes, failure modes) are in the experiment notes.

## Quick start

One command (needs a [Replicate API token](https://replicate.com/account/api-tokens)):

```sh
REPLICATE_API_TOKEN=... npx sprute "a small forest fairy with green wings"
```

Or set the key up once and forget it — `npx sprute login` walks you through it
(saved to `~/.sprute/credentials.json`, 0600), then just:

```sh
npx sprute "a goblin archer with a rusty crossbow"
```

The character is filed under a name derived from the description
(`a-small-forest-fairy`). Pass `--seed N` to reproduce a build, or `-r
./fairy.png` to steer from a reference image — or describe nothing and let the
reference carry the look. Every build also drops a `<name>.sprute.yaml` next to
the outputs with the name and seed baked in, so any one-off build re-runs
exactly:

```sh
npx sprute fairy.sprute.yaml
```

That same file is what you'd write by hand for a config-first workflow:

```yaml
# fairy.sprute.yaml
name: fairy
description: "A small forest fairy with green wings."
reference: ./fairy.png   # optional — omit to let the model invent the look
```

Project-wide defaults live in `./sprute.config.json` (`npx sprute init` writes
a starter); the merge order is flags > prompt > project config > builtin.

Either way the call composes the bundled 8-direction template, generates via
Nano Banana Pro, extracts and keys the sprites, and writes:

- `fairy.spritesheet.png` — 8 directions, one row
- `fairy.turntable.webp` — animated turnaround
- `fairy.concept.png` — the reference cell: for invented characters the model
  draws a full concept render there; for reference builds it's your reference
- `fairy.entity.json` — sprite metadata (directions, states, seed)
- `fairy.sprute.yaml` — flag builds only: the config that reproduces this build

After generation the views go back to the image model itself, laid out as a
labeled 3x3 compass grid: *"any errors? fix them and report the changes"*.
Anatomy glitches, wrong facings, parts that change shape mid-turnaround get
repaired in place — same character, defects fixed — and the model's text
report is printed. `--max-fixes N` sets the number of review rounds (default
1), `--no-check` / `check: false` skips review entirely.

The key can also live in a `.env` file in your working directory, or be saved
via `sprute login` (resolution order: env → `./.env` →
`~/.sprute/credentials.json`). Useful options beyond the basics (flag form /
config field form):

| flag | config field | default | meaning |
|------|--------------|---------|---------|
| `--seed N` | `seed` | random | a number reproduces a build; the seed used is recorded in `<name>.entity.json` |
| `-o dir` | `output` | `./outputs` / config's directory | where outputs land |
| `--sheet` | `outputs.sheet` | off | keep the raw generated sheet as `<name>.sheet.png` |
| `--template` | `template` | `8dir-v1` (bundled) | a builtin template name (`8dir-v1`, `8dir-v2`); config form also takes a full `{image, inputSlot, grid}` spec |
| `--provider` | `model.provider` | `replicate` | `google/nano-banana-pro` via Replicate (`REPLICATE_API_TOKEN`). Also: `gemini` (`GEMINI_API_KEY`), `novita-seedream`, `novita-qwen` (`NOVITA_API_KEY`) |
| `--matting` | `matting` | `toonout` | BiRefNet-ToonOut anime matting, run locally via onnxruntime (~440MB model auto-downloaded to `~/.cache/sprute` on first use); falls back to the Replicate endpoint (`REPLICATE_API_TOKEN`), then `floodfill`. `floodfill` = fast, dependency-free |
| `--no-check` | `check: false` | review on | skip the post-generation review/fix |
| `--max-fixes N` | `maxFixes` | `1` | review/fix rounds per build; each round feeds the previous round's output back |
| `--report` | `report: true` | off | stream a build log to `<name>.report.md` with every generated image inlined as a data URI |
| `--intermediate` | `intermediate: true` | off | write every intermediate image as numbered PNGs under `<name>.intermediate/` |

## Library

The CLI is the product, but the pieces it drives are importable too. Build a
character programmatically, or pull a single stage. Extraction and the
spritesheet QC check (`extractDirections`, `extractAnimation`,
`checkSpritesheet`) are library functions rather than CLI subcommands.

The matting model on its own:

```ts
import { toonoutMatting } from "sprute/toonout";
const matted = await toonoutMatting(cells); // RawImage[] in, RawImage[] out
```

It runs on onnxruntime (WebGPU first, CPU/WASM fallback); the model (~470MB,
[sprited/birefnet-toonout-onnx](https://huggingface.co/sprited/birefnet-toonout-onnx))
is fetched once on first use.

## Working from source

```sh
pnpm install
cp .env.example .env   # add your REPLICATE_API_TOKEN
pnpm cli examples/lisa.sprute.yaml
```

`examples/` is flat: each character is a config (`<name>.sprute.yaml`), its
reference (`<name>.reference.png`), and the outputs it produces
(`<name>.spritesheet.png`, `<name>.turntable.webp`, `<name>.entity.json`).
Copy an `.sprute.yaml` to start your own character.

The pipeline core (`src/core`) is pure TypeScript on `ImageData`-shaped
buffers — no Node APIs — so the same code runs in the browser; only file IO
and the model call (`src/node`, backed by sharp) are Node-specific.

The original Python lab scripts live on in `experiments/` as research notes.

## Status

Early research, moving fast. Current experiments:

| # | name | question | status |
|---|------|----------|--------|
| 001 | template-8dir | Can NBP fill an 8-direction sheet by analogy? | **works** — see notes |
| 002 | adaptive-chroma | Green-screen keying with drift-tolerant key detection | prototype |

Roadmap: walk-cycle templates, MCP server.

## Why open source?

See [docs/001-why-oss.md](docs/001-why-oss.md).

## License

MIT — except the Monet character assets in `examples/` (`monet.*`), which are
Sprited's character and for demonstration only. See [LICENSE](LICENSE).
