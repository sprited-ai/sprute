# PixelArtistry outreach

Status: **draft, not sent**. Jin reviews and sends.

## Who

[PixelArtistry](https://www.youtube.com/@PixelArtistry_) — 52.9K subscribers, 126 videos, weekly.
"Weekly videos about AI-powered 3D creation." Site: pixel-artistry.com.

What the channel keeps coming back to (recent titles, 2026-10):

- Animate ANY 3D Character From Just a Video (Free & Open Source)
- Rig ANY 3D Model Instantly with This Open Source AI! (6GB VRAM)
- Free Local Auto-Rigging & Animation is Finally Here!
- Generate Low Poly Characters on Only 6GB VRAM! (Free & Local)
- Claude Took Over ComfyUI + Blender: Here's What Happened

Pattern: open source, ComfyUI, "Free & Local", a VRAM number in the title,
one workflow shown end to end.

## Angle

Their videos end with an animated 3D character. Sprute starts there:
**any GLB motion → an 8-direction animated game sprite.** It's the next video in
their series, not a pitch for a different topic.

What lines up:

- `--motion` takes any GLB. A clip from their "animate from a video" episode can
  drive a Sprute character directly.
- `--image hero.png` takes any character render, so their AI 3D model can be the character too.
- ComfyUI under the hood, MIT, no API keys on the default path.

## Before sending (blockers)

1. **VRAM.** Tested on an RTX 5090 (32 GB); that's what the email says. Their audience
   is 6–8 GB, so the email says so up front rather than letting them find out on camera.
2. **Contact address.** Find the business email (YouTube "About" → business
   inquiries, or pixel-artistry.com). Don't use the newsletter form.
3. **Demo clip** below exists and is linkable (unlisted YouTube or GitHub Pages).

## Message (email)

**Subject:** Next step after your video-to-3D-animation episode: 8-direction sprites

> Hi PixelArtistry team,
>
> I'm Jin, I make Sprute, an open-source (MIT) tool that turns a prompt or a
> character image into an animated, 8-direction game sprite. It runs locally on
> ComfyUI with no API keys.
>
> I watched "Animate ANY 3D Character From Just a Video" and thought Sprute
> picks up right where it ends. Sprute's `--motion` takes any GLB, so a clip
> captured that way can drive a sprite character in eight directions:
>
> [30-second clip]
>
> If you'd like to try it, it's one command after setup:
>
>     sprute create character --prompt "a little knight with a red cape"
>
> Repo: https://github.com/sprited-ai/sprute
> Live demo (a small game made only from generated characters):
> https://sprited-ai.github.io/sprute/examples/brawler/
>
> Honest note on hardware: we've tested it on an RTX 5090 (32 GB). We haven't
> tried it on smaller cards yet, so it may not fit the 6–8 GB setups you usually cover.
>
> No strings attached. If you'd like to test it, I'm happy to help with setup
> or put together a workflow for your audience.
>
> Jin
> Sprited — sprited.ai

Notes on the draft:

- Mention one specific video of theirs, and keep it to one; it shows we watched without flattering.
- VRAM goes in the first message. Their brand is the VRAM number; finding out later costs trust.
- No ask for coverage or a fee. "Try it" is the whole ask.
- If there's no reply in ~10 days, send one follow-up with a new clip (e.g. their style
  of character → sprite). After that, stop.

## 30s demo plan

The goal: in 30 seconds, show *3D motion in → game sprite out* to a 3D-AI audience.
Built with the existing shorts pipeline (`tools/shorts`: asciicast → xterm.js stage → compose.py),
vertical 1080×1920 so it also works as a Short.

| Time | Shot | On screen |
|------|------|-----------|
| 0–3s | Hook | A 3D GLB mannequin doing a dance (`sprute render motion` cached webp), hard cut to the same motion as a pixel sprite in 8 directions. Caption: "3D animation → game sprite" |
| 3–9s | The input | `sprute generate motion --prompt "Gangnam style dance"` typed on the stage, fast-forwarded; the 8-direction GLB preview pops up |
| 9–16s | The character | `sprute create character --prompt "a little knight with a red cape"` (reuse `knight-create.cast`), turntable webp spins |
| 16–24s | The payoff | `sprute animate character --character knight --motion gangnam-style-dance`: the 2048×256 strip, then the big single-direction loop scaling up (`bigScale`) |
| 24–28s | In a game | 3 seconds of Sprute Brawl footage with generated characters |
| 28–30s | Card | "Free · Open source · runs on ComfyUI" + `github.com/sprited-ai/sprute` |

Production notes:

- New episode spec `tools/shorts/eps/05-glb-to-sprite.json`, modeled on `04-knight.json`.
- New assets needed: one generated dance GLB + its cached render, the knight animated with it,
  a Brawl screen capture. Knight character and turntable already exist in `tools/shorts/media`.
- Keep the speech-bubble lines from the series ("Chat, I want a knight.") but cut to 2–3;
  this clip is for a third party, not our channel voice.
- Optional variant for the follow-up email: swap the generated GLB for a clip captured from
  video (MoCapAnything path) to mirror their episode exactly.

### v1 (2026-10-28)

Built as two stage episodes joined end to end, since the stage plays one command per episode:
`tools/shorts/eps/05a-glb-motion.json` (prompt → GLB dance, 14 s) and
`tools/shorts/eps/05b-glb-to-sprite.json` (knight animated with that GLB, 15 s). 29 s total.

```bash
ffmpeg -f concat -safe 0 -i media/concat-05.txt -c copy media/short-05-glb-to-sprite.mp4
```

- Motion: `dance2` (prompt "a cheerful dance, arms swinging overhead, bouncing on both feet", seed 12),
  picked from five candidates. None actually reach overhead; dance2 was the liveliest.
- The animate run was recorded with `COMFYUI_RESERVE_VRAM=64` on gin's 96 GB card, leaving ComfyUI
  ~32 GB like a 5090. On screen: generate motion peaks at 1.5 GiB, animate at 31.7 GiB. Without
  the cap gin reports 59.6 GiB, which is what ComfyUI holds when it has room, not what it needs.
- Not in v1: the 0–3 s dance hook, Brawl footage, end card. The animate log shows one
  `[WARNING] aimdo:` line.
