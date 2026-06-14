# Product shape — Node library + CLI (2026-06-12, Jin)

**Two things, paired: a Node library and the CLI that drives it.** Nothing else
ships in v1. The web surface — browser pipeline, webUI, deployed demo page — is
**given up for now** (지금은 포기). Not killed; parked.

## The constraint: everything happens in the CLI

> **Every product capability is reachable from the CLI.** No capability lives
> only in a GUI or a web surface. Generation, fix rounds, QC, extraction,
> templates, the interactive session — all of it is CLI-driven.

The Node library is the *same engine* the CLI drives, exposed for embedding
(`import { buildCharacter } from "sprute"`). Library and CLI are one codebase:
the CLI is the surface, the library is its programmatic form. They ship as a
pair and stay in lockstep.

## What ships

| | what | status |
|---|---|---|
| **CLI** | `npx sprute "…"` — prompt-first ([`003`](003-cli-prompt-first.md)), aggregator-first (Replicate→Fal→Comfy, [`005`](005-byok-direction-from-mana-session.md)) | **the surface** |
| **Node library** | `sprute` core — the same engine, importable from Node | **paired with the CLI** |
| web lib / webgpu compute | `sprute/web` (onnxruntime-webgpu matting, canvas codec) | **parked, not deleted** — see future direction below |
| ~~webUI~~ | interactive web app / `sprute serve` | **parked** |
| ~~browser demo page~~ | `sprited-ai.github.io/sprute` — pipeline in the tab with a pasted key | **dropped** |

## Why drop the web surface (for now)

- **Focus.** One surface (CLI) + one library (Node) to make excellent.
- **The browser key problem.** The demo page ran the pipeline in the tab with a
  pasted key — and a provider token is a *spending bearer* (service_role-class)
  that must never sit in the browser ([`005`](005-byok-direction-from-mana-session.md)).
  Aggregator keys (Replicate/Fal) make the danger obvious where Gemini hid it.
  Parking the web surface sidesteps the problem entirely until it's worth solving
  with a server-side-local `sprute serve`.

## Out of scope — matting on Cloudflare (separate prototype)

Running the matting model (BiRefNet / ToonOut) on Cloudflare Workers is a
**separate prototype Jin is building on its own track** — not a sprute v1
concern, and not necessarily via `sprute/web`. `sprute/web` is parked (kept, not
deleted) to preserve the option; nothing about it blocks v1.

## Removal checklist (M1)

- [x] `demo/` vite app + `package.json` `dev` script + `.github/workflows/pages.yml`
      deleted (commit `2b6bc2a`).
- [x] `src/web/` kept, parked (not deleted) — source, tsup entries, and the
      `./web` / `toonout` browser exports left intact for a future off-browser
      revival. (Conservative reading of "parked, not deleted"; fully unpublishing
      the web export can happen later if it bit-rots.)
- [x] README synced to prompt-first + Replicate; demo/web sections dropped
      (commit `68d505a`).
- [x] Reddit draft [`002`](002-reddit-aigamedev-draft.md): browser-demo line
      removed; headline command → `npx sprute "…"`.
- [ ] **External (Jin):** take down the live page at
      github.com/sprited-ai/sprute → Settings → Pages. Deleting `pages.yml`
      stops redeploys; the current deployment stays up until removed there.

## Sequencing

M1 = CLI (Replicate lead) + Node library + this surface cleanup. The account /
broker / Cloud work ([`004`](004-comfy-gateway.md)) stays M2-parked.
