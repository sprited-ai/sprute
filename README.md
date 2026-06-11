# xsprite

Research sister project to [spritedx](https://spritedx.com) (private, for now).

## What this is

A headless, scriptable sprite-generation toolkit. Where spritedx is the
integrated SaaS experience, xsprite is the lab: new pipeline ideas get proven
here first, and the parts that survive graduate into spritedx — or, later,
into an open-source release.

Target shape (north star, not yet real):

```
xsprite character generate --batch 4 --dir 8 --reference ref.png --template template.png
```

## Strategy (decided 2026-06-11)

- **Build both.** spritedx (closed SaaS) and xsprite (research now, candidate
  open-core later) are sisters, not rivals.
- **The line, if/when we open: code open, weights + hosting closed.**
  Orchestration, frame extraction, templating → publishable.
  ACMv2 / BiRefNet Toonout finetunes, training data, augmentation recipes →
  confidential. Open CLI users still need inference tokens.
- Reddit signal (2026-06): "mind sharing your workflow?" ×4 — the workflow
  *is* a product. See `sprite-dx/docs/june-2026-reddit-signal.md`.

## Experiments

| # | name | question | status |
|---|------|----------|--------|
| 001 | template-8dir | Can nano-banana pro (et al.) fill an 8-direction character grid by analogy from a cam2portrait-style template? | designing |
