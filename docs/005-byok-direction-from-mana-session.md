# BYO-key direction (notes from the 2026-06-12 mana session)

> **Status: reconciliation notes.** Captured from a design conversation in the
> `~/dev/mana` repo session on 2026-06-12, handed off here. The provider half of
> the open question is now **RESOLVED** (see below); the M2/OAuth half stays
> parked. Does **not** overwrite [`004-comfy-gateway.md`](004-comfy-gateway.md).

## RESOLVED — provider surface (2026-06-12, Jin)

This supersedes [`003`](003-cli-prompt-first.md)'s "two doors (Gemini BYOK +
Sprited Cloud), no Replicate/fal in v1." v1 goes **aggregator-first**:

- **Provider priority: Replicate → Fal → Comfy** (+ own-ComfyUI endpoint).
  One key → many models, including the **video** models walk-cycles need.
- **Gemini-direct: dropped from the v1 doors**, not killed — fine to bring
  back as an **option later**. Reason it's not a v1 door: it can't carry the
  roadmap (no video; `-preview` churn; per-vendor prepay).
- **Markup: accepted** for the default aggregator path — the price of their
  vendor BD/ToS deals ("legitimacy outsourcing"), not a blocker. The **no-markup
  escape hatch** is the own-ComfyUI pick: a user who wants to spend their own
  per-vendor keys directly runs ComfyUI + [comfy-api-liberation](https://github.com/holo-q/comfy-api-liberation)
  on their box and configures sprute to point at it. Later, advanced, user-side —
  sprute just exposes the endpoint/key config; it never holds vendor keys itself.
- **seedream silent-fallback footgun: mitigated in code.** sprute always pins
  the explicit model id and validates the response's `model` field; it never
  relies on an aggregator's default route. So a silent model swap — real or
  not — can't reach the template trick.
- **Still open (M2):** 004's OAuth/broker/custody/Cloud — untouched today,
  stays demand-gated. See the M2 question below.

## The (remaining) open question — M2

`004-comfy-gateway.md` plans a Sprited-account **broker** + server-side Comfy
key **custody** + real **OAuth** + paid **Sprited Cloud** (its M2). In the mana
session Jin said he wants to **give up the OAuth flow** and just have users put
the key in env / a local secret (BYO-key).

**Is OAuth/broker (004's M2) dropped permanently, or just deferred?**

- These are reconcilable: today's direction = ship **004's M1 (BYO-key)** as the
  whole v1 product; defer **M2 (broker/OAuth/custody/Cloud)** until library
  developers actually demand it. 004 itself sequences M1→M2 and already calls
  BYOK a "permanent escape hatch," so this is a scoping-down, not a reversal.
- The only thing that changed is **emphasis + timing**: M1 is the product;
  M2 is demand-gated, not the near-term plan.

Until Jin answers, treat the below as "the BYO-key v1 shape," with M2 parked.

## BYO-key v1 shape (what the mana session converged on)

- **Liability/responsibility = flow-down.** Local CLI + BYOK webUI: end user,
  own key, own machine → zero Sprited backend, zero liability. As a library:
  scaling + ToS + key custody + provider deals are the **embedding developer's**
  responsibility, not sprute's. sprute = LICENSE + a short "responsibilities"
  note; never phones home, never stores keys centrally.
- **webUI / browser: parked** ([`006`](006-product-surfaces.md)). v1 is Node
  library + CLI only. This sidesteps the hard problem rather than solving it: no
  real browser secret store exists (Credential Management API = login creds only;
  localStorage/IndexedDB = plaintext; Web Crypto wraps at-rest, not in-use), and
  a provider token is "service_role"-class (a spending bearer, no per-row authz)
  you must never put in a browser. If the web surface returns, the key stays
  server-side-local (`sprute serve`-style); the browser never holds it.

## Provider backends (reconcile with the existing `--provider` abstraction)

The repo already has `--provider gemini|novita-seedream|novita-qwen` (+ Replicate
for matting fallback). The mana session framed the **inference** backends as a
"user picks ONE key" set, to avoid the "N provider keys = complex" problem:

| pick | one key → | notes |
|---|---|---|
| **Replicate** | many | good portal, **has markup**; has Nano Banana + Seedance 1 Pro (~$0.57/1080p·5s) + Flux |
| **Fal.ai** | many | good portal, fast, markup; Nano Banana Pro ~$0.15/img, NB2 ~$0.08; Seedance 1 Pro ~$0.62 |
| **comfy.org** | ~40 providers | **passthrough, no markup**, broadest; weak portal; per-provider response shapes. Adapter ≈ lift the Phase-1 tracer from `~/dev/mana` (`src/lib/comfy.ts`, `/proxy/*` + `X-API-KEY`) |
| **own ComfyUI** | (endpoint + workflow) | sprute = thin ComfyUI API client (`POST /prompt` → poll `/history` → `/view`). User may add [comfy-api-liberation](https://github.com/holo-q/comfy-api-liberation) on their box to break the comfy.org proxy and use their own vendor keys direct — **user-side, not sprute's concern** |

Note vs. README today: the README's default is **Gemini-direct** (Nano Banana
Pro). Gemini-direct stays the simplest path; Replicate/Fal/comfy are the
"one key, many models (incl. video for walk-cycles)" options. Open: which of
these ship in v1 vs. later.

Aggregator markup (Replicate/Fal) = the price of *them* having done the
provider BD/ToS deals (they're on BFL's partner list). It's "legitimacy
outsourcing" — a reason to use them rather than chasing per-vendor deals yourself.

## First-run UX (proposed, mana session)

`npx sprute` first run, Claude-Code-style (aligns with `003-cli-prompt-first-jin.md`):

```
How do you want to use sprute?
  1. Replicate API key
  2. Fal.ai API key
  3. Comfy API key (one key, ~40 providers, no markup)
  4. Your own ComfyUI (URL + auth header)
  → (links to docs for each)
```

## Where the deeper legal/prior-art analysis lives

`~/dev/mana/docs/notes/2026-06-12-legal-positioning-memo.md` and
`~/dev/mana/docs/legal/prior-art/` (30+ companies; the three-archetype model:
A = host open weights, B = BYO-key pass-through, C = resell closed API for a
margin). Backends 1–2 = C, 3 = C(passthrough), 4 = A.
