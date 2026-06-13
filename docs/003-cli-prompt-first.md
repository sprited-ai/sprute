# Proposal: prompt-first CLI

> Canonical version. Raw source notes: [`003-cli-prompt-first-jin.md`](003-cli-prompt-first-jin.md).

Zero users yet — redesign the surface instead of bolting onto `gen char`.

## The surface

```sh
npx sprute "a small forest fairy"           # generate using defaults
npx sprute generate "a small forest fairy"  # explicit form of the same
npx sprute                                  # interactive session — Claude Code for sprite gen
npx sprute init                             # write ./sprute.config.json
npx sprute login                            # first-run auth, Claude Code style
```

## Decisions (2026-06-12, Jin + Monetto)

- **Login menu v1 = two doors:** Gemini API key (BYOK, default) or
  Sprited Cloud (no key, billed by Sprited — M2). No Replicate/fal in v1
  (+12-25% markup, silent seedream fallback footgun, niche audience);
  add aggregator keys when users ask. Comfy key only helps users already
  running ComfyUI — "coming" at best.
  > **SUPERSEDED (2026-06-12, Jin) →** v1 goes aggregator-first:
  > **Replicate → Fal → Comfy** (+ own-ComfyUI). Gemini-direct drops from the
  > v1 doors (later option, not killed); markup accepted; the footgun is
  > handled in code (pin model id + validate response `model`). Full
  > resolution in [`005`](005-byok-direction-from-mana-session.md#resolved--provider-surface-2026-06-12-jin).
- **Money placement:** the act of paying never happens on OSS surfaces
  (CLI, sprute.dev) — always link out to sprited.ai. The fact that money
  is involved is never hidden: every option is labeled "billed by X"
  (Google / Sprited). Comfy's hide-the-payment approach produced
  confusion, not trust — the OSS allergy is to cash registers in the
  tool and to disguise, not to the word "paid".
- **Doors vs pool:** login doors are product-branded (auth.sprute.dev
  for sprute; spritedx.com keeps its own door) because users trust the
  brand in their hand — an unknown umbrella domain reads as phishing.
  The user pool underneath is one company pool (the existing spritedx
  Supabase), so the account graph accrues to Sprited. "operated by
  Sprited" appears as the nameplate, not the door.
- **Sprited Cloud is M2, not "later":** BYOK-only v1 abdicates the
  funnel — key acquisition is the #1 drop-off, and most users take the
  easy paid path (Claude Code model). Cloud must be more than re-billing:
  instant no-key start, GPU matting (local Apple-GPU webgpu ≈ 2.9s/cell
  ≈ 22s/build; CUDA is ~100x), build history, never silently swaps
  models, bridges to SpriteDX.
- **comfy-api-oauth:** a flag, not a project. Comfy (for-profit, $500M
  val) has no developer on-ramp at all — no payment docs, no app
  concept, no OAuth; its monetization assumes you're inside the app. RFC
  one-pager + public Comfy-Org discussion ("the missing developer
  on-ramp; we bring the game-asset vertical as first client"), code only
  on signal. Never under the OSS-neutral hat — we enter as contributor.
- **Sequencing:** M1 prompt-first CLI ships first and unblocks the
  Reddit post; npm publish happens after M1 so the announced command is
  the final surface.

No other subcommands. `gen char`, `build`, `-d`, `extract`, `extract-anim`,
`check`, `completion` all die from the CLI (extraction/QC stay importable
from core — the pipeline uses them).

Dispatch for the first argument: known command (`generate`, `init`,
`login`) → that command; ends in `.yaml`/`.json` → config-file build
(reruns a saved `<name>.sprute.yaml` exactly, no project-config merge);
starts with `-` → flags-only build (e.g. `-r ref.png`); anything else →
it's the character description; absent → interactive session.

`sprute.config.json` = project defaults, vite-style, same shape as the
character yaml. Merge precedence: `flags > prompt > sprute.config.json >
builtin`. Flag builds keep dropping `<name>.sprute.yaml` next to outputs.

## Login experience

First-run should mirror Claude Code: run it, get walked into auth, never
think about it again.

```
$ npx sprute "a goblin archer"
  ▌ sprute needs an image-model key (one-time setup)
  ▌ 1. Gemini API key   — aistudio.google.com/apikey (Nano Banana Pro)
  ▌ 2. Comfy API key    — platform.comfy.org (coming)
  paste key: ****
  ✓ key works (gemini-3-pro-image-preview reachable)
  ✓ saved to ~/.sprute/credentials.json (0600)
```

Key resolution order: `GEMINI_API_KEY` env → `./.env` →
`~/.sprute/credentials.json`. `sprute login` re-runs the flow; env always
wins so CI stays simple. Honest framing: today this is key management,
not OAuth — Gemini has no OAuth-for-API-key flow. The word `login` still
earns its name as the guided first-run.

## COMFY_ORG_API_KEY — research findings (2026-06)

The attraction: Comfy's partner-node program routes many paid models
through **api.comfy.org** with one account key and a credit balance billed
at vendor price — and **Nano Banana Pro is among the partner nodes**. One
`COMFY_ORG_API_KEY` would cover NBP today and Seedream/Kling/etc. later.

What the research says:

- **Officially supported shape:** a running ComfyUI server executes a
  workflow JSON; the key rides in `extra_data.api_key_comfy_org` on
  `POST /prompt`. Headless is first-class (the UI is just a client), but
  it is still *your* ComfyUI process — python + torch, multi-GB install.
  Too heavy to bundle in an npx tool; fine to *point at* if the user
  already runs one (huge install base, plus our own comfy.sprited.ai).
- **Direct api.comfy.org calls without ComfyUI:** the API nodes hit
  `/proxy/<vendor>/...` endpoints — the shape is known (the
  comfy-api-liberation project rewrites them) — but it's **undocumented
  for third-party apps**. Using it would need a conversation with Comfy
  Org first; that's the "lightweight association" cost, and it cuts both
  ways: their branding on our CLI, our dependence on their credits.

**Recommendation:** ship Gemini-direct as the default now. Add a `comfy`
provider that submits a partner-node workflow to a configurable ComfyUI
endpoint (`COMFY_URL`, default localhost:8188) — light for us, works
today, no permission needed. Talk to Comfy Org about direct proxy access
before building anything npx-light on api.comfy.org.

## Interactive session (bare `sprute`)

The Claude Code-shaped REPL. MVP loop:

```
> a goblin archer with a rusty crossbow
  … generating · matting · self-review … ✓ goblin-archer (seed 841422)
> make the crossbow bigger and add a quiver
  … fix round on the same sheet … ✓
> /reroll        # fresh seed, same description
> /save outputs/
```

The fix loop already exists in the pipeline (`fixSpritesheet` takes
instructions); the session just exposes it conversationally. Later:
gallery of past builds, template switching, walk-cycle states.

## Milestones

1. **M1** — prompt-first dispatch + `init` + `login`/keystore (Gemini)
2. **M2** — interactive session
3. **M3** — `comfy` provider (BYO ComfyUI endpoint, partner-node workflow)

Touches: `src/cli.ts` rewrite, `src/node/completions.ts` delete, keystore
module, README/demo/Reddit draft headline → `npx sprute "a small forest fairy"`.
