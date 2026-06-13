# Comfy connection — Sprited account as the broker (+ RFC to Comfy-Org)

> **M2-parked (2026-06-12).** v1 is Node library + CLI with BYO aggregator keys
> ([`006`](006-product-surfaces.md)). Everything in this doc — Sprited account,
> broker, OAuth, key custody, paid Cloud — is M2, demand-gated, behind v1.
> Recorded, not scheduled.

Revision note (2026-06-12): an earlier draft proposed "comfy-gate", a
Comfy-branded open-community auth gateway. Killed — using their brand on
a service that custodies user keys is a trademark and accountability
mistake, and "community" dress over Sprited-run infra is exactly the
disguise we said we'd avoid. Credential custody needs a named,
accountable operator. The broker is Sprited account infrastructure,
honestly labeled. (This lands back on Jin's original instinct: hand the
Comfy connection to our backend and wrap it in OAuth ourselves —
the fenn/SnapTrade pattern.)

## The structure

```
Sprited account (sprited.ai)
  └─ Connections
       · Comfy account   — user registers their COMFY_ORG_API_KEY once;
                           our backend submits partner-node workflows with
                           the key in extra_data (documented usage);
                           model billing stays user ↔ Comfy. FREE.
       · Gemini key      — optional server-side storage of a BYOK key
       · Sprited Cloud   — the only PAID thing: no keys at all, we route
                           and bill, GPU matting, churn absorption
```

- Apps (sprute first) do real OAuth against the Sprited account — real
  because we issue the tokens. Device flow for CLIs.
- Per-app attribution, spend caps, revocation — the sub-app concept Comfy
  lacks, implemented at our layer until they ship it natively.
- Connection brokering is free, forever — pass-through, not resale. The
  CoI line holds: Sprited never marks up someone else's model bill.
- Doors stay product-branded (auth.sprute.dev skin for sprute users),
  pool is the one Sprited account system underneath, "operated by
  Sprited" on the nameplate.

## Why Comfy connection matters (and why not Gemini alone)

Gemini won't carry the roadmap: walk cycles / animation states point at
video models (Kling/Veo/Wan), pose control at diffusion stacks — much of
it living in ComfyUI as the runtime, one Comfy key away via partner
nodes. Both vendor doors wobble (Google: -preview churn, per-vendor
prepay; Comfy: in-app wallet, policy risk). The stable layers are
sprute's pipeline spec and the Sprited account absorbing churn for
paying users.

## The Comfy gap (for the RFC — stays a neutral public proposal)

Comfy Org ($500M val, partner nodes routing real money) has no developer
on-ramp:

- **No web payment** — credits are bought inside the ComfyUI app only.
  A CLI/web user who never installed ComfyUI cannot top up. This is the
  single biggest blocker; their world model assumes users live in the app.
- **No app concept** — one user key used by five tools = five
  indistinguishable callers.
- **No OAuth** — third-party apps can only ask for pasted raw keys.

The ask, as a ladder:

```
0. Web payment on platform.comfy.org   — without this nothing else matters
1. App-tagged API keys                 — attribution & revoke; one column + a dashboard
2. OAuth (sub-apps, scopes, caps)      — the Facebook-platform moment
```

Stage-2 consent should look like open banking (apps spend money, not
just read data):

```
  sprute wants to: know who you are · generate with partner models
  using your credits · see your balance · spend ≤ 500 credits/month
```

What's in it for Comfy: app-spend dashboards, partner leverage,
leaked-key forensics, an app directory — the store, not just the
runtime. We offer to contribute the open parts (ComfyUI-side token
handling, client libs; their repos are GPL/open) — only the closed parts
(platform.comfy.org, api.comfy.org) need their hands. When they ship
natively, our broker swaps pasted keys for their OAuth underneath the
same Sprited connection — users notice nothing.

## Honest risks

- We custody user Comfy keys server-side — encrypted at rest, named
  operator, real terms. Better one accountable vault than keys pasted
  into N tools, but it's still a vault: scope it, audit it.
- Third-party custody of keys is ToS-gray — an explicit agenda item for
  the Comfy-Org conversation, not hand-waved.
- Platform dependency (the Zynga lesson): Gemini-direct BYOK stays a
  permanent escape hatch; Comfy is one backend among several.

## Sequencing

Unchanged: M1 (prompt-first CLI, Gemini BYOK) → M2 (Sprited Cloud +
account/connections) → RFC discussion post to Comfy-Org after sprute is
public. Nothing here blocks M1/M2.
