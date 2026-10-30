# Spike: build the character in 3D, render it to 2D sprites

2026-10-29, branch `claude/spike-3d-render-9a7d2e` (on top of PR #21, `claudia/monster-quadruped`).
Prototype: `tools/render3d/paint_rig.py`. Images: `docs/spikes/3d-render/`.

**Verdict: go, as a third animate backend (`--use render`) for monsters with a rig, not as a new pipeline.**
The riskiest assumption held on the first run: a design painted over a rig's pose, projected back onto the rig,
renders through every clip in Sprute's look, with no seed lottery. The first real step is in
[Recommendation](#recommendation).

![The dusk wolf: NBP design (top), the same design projected on the husky rig and rendered (bottom)](3d-render/directions.png)

## Problem

Sprute makes a character in 2D: generate (flux-fill) → AniSora turntable (directions strip) → SCAIL2 animates it,
driven by a GLB motion rendered on Template-kun (or, since PR #21, on the GLB's own body). Its weak spots are all
consequences of a video model drawing every frame:

- **Seed lottery.** Melting, ghost legs (the dusk wolf's gallop ghosted at seeds 11 and 12), facing flips (head
  turning, `TASKS.md`). `--attempts` and `sprute check` pay for retries; the check can't see ghost legs.
- **Body shape is bounded by the driver.** SCAIL2 follows a mesh render, so anything with a rig works, but the
  character must fit the driver's silhouette.
- **No exact direction consistency.** Each direction is drawn separately; a badge on the left shoulder can swap sides.

Materia meanwhile built a monster directly in 3D and baked it to 2D. Jin wants to know how Sprute would offer that
"made in 3D, shown as 2D" structure itself.

## What already exists

### Materia's stubby (PR 142, `feat/monster-3d`, merged)

| | |
|---|---|
| **Model** | Modelled **in code** (three.js primitives, lathes, rounded boxes in `packs/monsters/view/stubby.ts`), no generator. |
| **Rig / animation** | None. Procedural: bob, look around, a waddle driven by the speed it moves; antenna and strap tails are Verlet chains (`Dangle`), which the sibling session *Cloth & hair sim* generalises to chains and cloth in `packs/monsters/view/soft.ts`. |
| **Bake** | `npm run bake <id>` → `tools/bake/bake.ts` in headless Chrome. Orthographic camera, 15° pitch (Sprute's), light from the front that turns with the camera, toon ramp (3 tones) plus a stepped matcap for bare metal. Line art from silhouette (alpha), depth steps (3 cm), folds (normals > 60°) and material boundaries, drawn by distance so every line is the same width and anti-aliased. Rendered at 352, shrunk to 176, grown back to 256 to be "soft and low-res like the Sprute sheets". |
| **Output** | 8-row atlas, only rows 1/3/5/7 (diagonals) filled, 256 cells, 12 fps, idle 36 / walk 8 / run 8, WebP, `manifest.json` with `directions: 4`, anchor and figure height measured from the render. |
| **What broke** | Colours came out dark (linear render target read as sRGB; fixed in 7548fb3, Jin: "아직도 어두워" until then). Lines thick in one place and thin in another until they were drawn by distance. Light from the upper left didn't match the heroes. |
| **What Jin liked** | "이 방향 좋아", "훨 귀여워", the tin-can version: "지금 디자인 너무 좋아 … 메인에 머지하고 싶어". Wants anti-aliased outlines, not pixel art, so it matches Sprute characters. Recolour (band, eye) parked in TASKS as a paint-mask idea. |

Lesson for Sprute: the look is the hard part, not the plumbing, and Jin already approved one answer to it
(front light, even AA ink, soft downscale). The modelling method (code) doesn't carry over: Sprute users bring an
image, not a three.js file.

### Sprute

| Piece | Where | What it gives a 3D path |
|---|---|---|
| Renderer | `custom_nodes/sprute/renderer.py` | Skins any GLB in PyTorch and rasterises it with ComfyUI's rasteriser. Same camera as every Sprute character (15°, ortho, 180.5 px/m). **This is the 3D path's renderer already** — the prototype only changes its shading. |
| Own-body rigs | PR #21: `--motion rig.glb [--clip X] [--own-body]`, `Model.fit`, `motion_file.own` | Loads non-humanoid rigs and their clips (Quaternius husky: Idle, Walk, Gallop, Attack, …). |
| Paint-over design | `experiments/monster-quadruped` (`rigpose.py`, `todirs.py`, `p-wolf.txt`) | NBP paints the monster over a 2x2 render of the rig's first Idle frame, so the design already stands in the rig's pose (IoU 0.91). **This is what makes projection possible.** |
| 4-direction layout | `layout.py`, `--directions 4`, `--cell` (feat/monster) | Strip format: 8 cells, S E N W transparent, 12 fps. |
| Check | `sprute check animation --directions 4` | Identity/facing/coverage/colour per direction. |
| Atlas | Materia `tools/pack-atlas.py`, `check-atlas.py` | Strip → atlas + manifest. |
| TRELLIS.2 | `feat/3d-asset`, memory `trellis2-props` | Image → textured mesh on gin, 273 s bf16. Texture "too smooth" and dark next to sprites; decimation shreds below ~5k faces. No rig. |
| MoCapAnything | `feat/mocap-anything-v2` | Video → clip on the husky rig. New clips for a rig. |
| Kimodo | `character-motion` | Text → humanoid clip. |
| `--use` backends | PR #24 (`--use seedance`) | Precedent for swapping SCAIL2 inside animate. |

(There is no `feat/3d` branch locally or on origin; `feat/3d-asset` is the 3D work.)

## Options

### Where a 3D path plugs into the CLI

| Option | For | Against |
|---|---|---|
| **A. `create character --use 3d`**, a whole new pipeline | One command | Duplicates generate/turntable/animate; the 2D steps it replaces are only *animate*. |
| **B. A separate `sprute render` command** | Clear that no model runs | A second way to make the same strip; `--attempts`, `--directions`, `--cell`, check and preview would need wiring twice. |
| **C. `animate --use render`**, a backend beside SCAIL2 and Seedance (recommended) | Same inputs (directions strip + `--motion rig.glb --clip X`), same output strip, same check and atlas. PR #24 set the pattern. | Only valid when the directions strip was painted over that rig — needs a guard (below). |

C plus one design step. The design has to be painted over the rig's pose, so the character is made from the rig,
not the other way round:

```
sprute create character --body husky.glb --prompt "dusk wolf…"   # renders the rig's pose sheet, paints over it (NBP / flux-fill)
sprute animate character --character dusk.directions.png --motion husky.glb --clip Walk --use render
```

`--use render` refuses a directions strip whose silhouettes don't match the rig's pose render (IoU < 0.85 in any
direction), because projection then paints the wrong parts. The dusk wolf's design is at 0.91–0.92.

### Image → mesh → rig → animate → render, and which tools

| Stage | Options | Pick |
|---|---|---|
| Mesh | (1) a **template rig's own mesh** (Quaternius CC0 animals, Template-kun); (2) TRELLIS.2 from the design; (3) Tripo/Meshy (paid, external); (4) modelled in code (Materia) | (1) now. (2) as the next step, when the silhouette must be the design's (see *What it loses*). |
| Rig | (1) the template's own; (2) **skin-weight transfer from the template** onto a TRELLIS mesh — it is generated from a design already standing in the template's pose, so nearest-surface transfer (Blender *Data Transfer*) needs no posing; (3) UniRig / Tripo auto-rig | (1) now, (2) next. Auto-riggers are for shapes no template fits. |
| Texture | (1) **projective paint from the design views in the reference pose** (prototype); (2) TRELLIS's own texture | (1). It carries the painted style and needs no UVs. TRELLIS textures are de-lit and smooth (measured 58–78 % luminance). |
| Animation | rig clips (Quaternius), MoCapAnything (video → clip), Kimodo (humanoids), procedural (Materia's waddle, slimes) | All already exist; nothing new. |
| Render | Sprute's renderer + the shading in `paint_rig.py`; Materia's bake (three.js, headless Chrome) | Sprute's renderer: Python, no browser, runs where ComfyUI runs, already shares the camera. Port Materia's fold/material lines into it later. |

### Keeping the look consistent with 2D-path characters

The prototype takes four choices from the Materia bake and Sprute's renderer:

1. **Paint, not shading.** The colour is the design's own painting, so it carries NBP's style and light the same
   way SCAIL2 output does. No relighting, so no "too dark" problem.
2. **Same camera.** `renderer.camera` and `PIXELS_PER_METRE` — feet and size land where SCAIL2's do (the render
   overlaps the design at IoU 0.93 in rest pose; Materia measures the same anchor for both wolves).
3. **Even, anti-aliased ink** on silhouette and depth steps, rendered at 3x and averaged down (Jin's ask for the
   stubby: AA outline, not pixel art).
4. **Soft**: the 3x supersample averages to 256. Materia's 176 → 256 round trip is one line to add if it reads
   too crisp next to SCAIL2.

## Prototype

**Riskiest assumption:** that a rigged mesh can wear a 2D design well enough to pass as the 2D path's character
in every frame. Plumbing (strip layout, check, atlas) was never the risk — Sprute already renders GLBs. The look
was: Jin rejected a painterly 3D render for the tin, TRELLIS textures for props, and only accepted the stubby after
the bake learned Sprute's look. If a generic rigged mesh can't look like the design, the rest of the design is moot.

**What ran:** `tools/render3d/paint_rig.py` on the husky rig (Quaternius CC0, from PR #21) and the dusk wolf's
NBP design (`experiments/monster-quadruped/design/dusk.directions.cut.png`), the same inputs that made the SCAIL2
dusk wolf. For every pixel the rasteriser covers, the surface point is looked up in the reference pose (Idle,
frame 0, the pose the design was painted over), projected into each of the four design views, and coloured from the
views that see it (depth-tested against that view, weighted by how squarely it faces it). The paint then rides the
skin through any clip. ~120 lines, CPU only, on the Mac.

```
python tools/render3d/paint_rig.py husky-b.glb dusk.directions.cut.png out --name dusk \
    --clip Idle:40 --clip Walk:12 --clip Gallop:6
```

### Results

Walk and gallop, SCAIL2 above, 3D render below (SE NE NW SW):

![walk](3d-render/walk.gif) ![gallop](3d-render/gallop.gif)

Every frame: [walk](3d-render/walk.png), [gallop](3d-render/gallop.png). The gallop is where SCAIL2 ghosted legs
at seeds 11 and 12 and drew front legs touching at 13 (the one kept); the render has four distinct legs in every
frame, first try.

Eight directions from the same four paintings (`--directions 8`; S, E, N, W were never painted):

![eight directions](3d-render/eight.png)

**`sprute check animation --directions 4`** (on gin, against the design's directions strip): every direction of
every clip passes. Next to the SCAIL2 wolf's numbers from PR #21:

| clip | identity min | facing min | coverage | colour max |
|---|---|---|---|---|
| idle, SCAIL2 s11 | 0.960 | +0.030 | 0.985–1.014 | 0.016 |
| idle, 3D | 0.872 | +0.034 | 0.986–1.020 | 0.041 |
| walk, SCAIL2 s11 | 0.958 | +0.027 | 0.912–1.014 | 0.025 |
| walk, 3D | 0.851 | +0.031 | 0.872–0.992 | 0.041 |
| gallop, SCAIL2 s13 (kept) | 0.943 | +0.007 | 0.926–1.020 | 0.012 |
| gallop, 3D | 0.809 | +0.024 | 0.828–0.966 | 0.040 |

Read honestly: the render faces the right way with more margin than SCAIL2 (gallop +0.024 vs +0.007), but it is
*less like the design* (identity 0.81–0.87 vs 0.94–0.96). That is the silhouette loss below — the husky's head,
ears and missing mane — plus the darker ink line raising the colour distance. The check can't see ghost legs, so
it can't credit the render for having none.

**Materia accepts it.** `tools/pack-atlas.py --motions tools/tin-motions.json` packs the 3D strips like the
SCAIL2 ones, anchor [96, 184] in both, figure height 151 vs 150 px, and `tools/check-atlas.py` reports ok for
both. (At 256 px a 40-frame idle is 10240 px wide, over the packer's 8192 limit, for either wolf; packed at
`--scale 0.75`.)

### Next step tried: a TRELLIS.2 mesh on the rig

Branch `feat/3d-render` (worktree `~/dev/sprute-3d-render`). `tools/render3d/trellis_shape.py` runs TRELLIS.2 on
gin with shape only (30 s; the paint comes from projection), from one design view (SW, and SE). Then
`tools/render3d/rig_mesh.py` turns, scales and moves the mesh onto the rig's reference pose by matching silhouettes
to the design (yaw search, then coordinate descent on scale, offset and pitch). Each vertex takes the skin weights of
the nearest point on the husky's surface (median 1.1 cm away, 95 % within 4 cm), and is moved into bind space.
`paint_rig.py --body` then renders it.

Fit, design green, mesh magenta, overlap white (SW-view mesh):

![fit](3d-render/trellis-fit.png)

Design / husky mesh / TRELLIS mesh on the husky rig:

![trellis directions](3d-render/trellis-directions.png)

| mesh | IoU to the design, SE NE NW SW |
|---|---|
| husky (prototype) | 0.936 0.929 0.928 0.936 |
| TRELLIS from SW view | 0.789 0.809 0.808 0.790 |
| TRELLIS from SE view | fit only 0.68 at 128 px; not rendered |

- **The weight transfer works.** The gallop plays with four clean legs, nothing tears, and the mane now has geometry
  and moves with the neck ([every frame](3d-render/trellis-gallop.png)).
- **The single-view mesh doesn't.** TRELLIS invents the head's angle from one 3/4 view, and it disagrees with the
  other three paintings. The projected paint then lands wrong (an eye on the forehead, a dark snout), and
  surfaces no view sees (the top of the tail) go dark. IoU falls from 0.93 to 0.80.
- ComfyUI 0.37's native TRELLIS.2 nodes take one image; there is no multi-view conditioning to fix this.

### The recommended step: the husky's own mesh fitted to the design's silhouette

`tools/render3d/fit_silhouette.py` keeps the husky's vertices, faces and skin weights, and pushes each vertex along its
normal in the reference pose until the outline matches the design's in all four diagonals (Adam, 400 steps, 45 s on
the Mac): outline vertices are pulled onto the zero of the design's signed distance field, every pixel of the design's
outline pulls the nearest outline vertex (so a spike of fur with no vertex near it still gets one), and a smoothness
term spreads the push. `--subdivide 1` first splits each triangle in four (3.9k → 8.7k vertices, weights interpolated)
so the mane has vertices to grow. Then `paint_rig.py --body`, as for the TRELLIS mesh.

```
python tools/render3d/fit_silhouette.py husky-b.glb dusk.directions.cut.png dusk-fit.npz --smooth 3 --subdivide 1
python tools/render3d/paint_rig.py husky-b.glb dusk.directions.cut.png out --name dusk --body dusk-fit.npz \
    --clip Idle:40 --clip Walk:12 --clip Gallop:6
```

Design green, mesh magenta, overlap white; husky above, fitted below:

![silhouette fit](3d-render/fit-silhouette.png)

| mesh | IoU to the design, SE NE NW SW |
|---|---|
| husky | 0.913 0.918 0.918 0.912 (at 256 px; 0.93 at 128) |
| fitted, no subdivision | 0.958 0.959 0.953 0.959 |
| fitted, `--subdivide 1` | 0.958 0.961 0.958 0.957 |

The fit stops at ~0.96: what is left is under a pixel along the outline (at 256 px one pixel all round is 6–8 % of
IoU), plus places where the four paintings don't agree with each other as one solid.

A gallop frame (index 2) from each path; every frame of every clip was looked at:

![comparison](3d-render/fit-compare.png)

`sprute check animation --directions 4`, against the design's strip, all pass; identity min per direction (SE NE NW SW):

| clip | SCAIL2 | husky + paint | TRELLIS + husky weights | husky fitted |
|---|---|---|---|---|
| idle | 0.960 | 0.872 | – | 0.930 0.890 0.888 0.938 |
| walk | 0.958 | 0.851 | 0.885 0.883 0.866 0.887 | 0.919 0.901 0.894 0.935 |
| gallop | 0.943 (s13, the kept seed) | 0.809 | 0.835 0.868 0.835 0.884 | 0.910 0.882 0.853 0.932 |

- **The fit helps**: +0.03–0.08 identity over the husky mesh in every clip, more than the TRELLIS mesh, with the
  husky's head and rig kept. The mane and neck read as the design's.
- **The skinning holds.** No tears and no ghost legs in any frame of the three clips; the pushed vertices keep their
  own weights, so nothing moves with a bone it didn't before. Gallop NE frames 3–4 cross a front and a hind leg, as
  the husky mesh does: that is the clip, not the fit.
- **0.97 identity is out of reach for this render, whatever the shape.** The reference pose itself — the very pose the
  design was painted over, silhouette IoU 0.96 — scores 0.942 0.903 0.902 0.951 (husky mesh: 0.936 0.889 0.883
  0.941). Drawing it with no ink line at all only lifts NE to 0.926. What keeps it under is the look: projected paint
  on a mesh, flat lit, against a painting. SCAIL2 is closer (0.94–0.96) because it repaints every frame in the
  painting's style, and that is also where its ghost legs come from.

So the silhouette is now the design's; the look is the next gap, and it is a 2D one (a restyle pass over the rendered
frames, conditioned on the design, with the render as structure), not a mesh one.

### A Materia machine from one image: the stubby

Jin, after the wolf: try a Materia machine monster, starting simple. The stubby is Materia's code-modelled machine
(PR 142) whose bake Jin approved, so its bake is the ground truth: can Sprute get back to it from one image?

One image (the bake's SE idle frame, 256 px upscaled to 1024) → TRELLIS.2 with texture (120 s on gin) →
`tools/render3d/render_mesh.py`: fitted to the bake's four silhouettes (`--yaw 0`: the front and back silhouettes are
nearly the same, so the fit alone can't tell which way it faces), drawn in Sprute's camera and line art. Static, no
rig yet.

Materia's bake / TRELLIS's own texture / TRELLIS's shape painted by projecting the bake's four views:

![stubby](3d-render/stubby.png)

- **TRELLIS's shape is usable.** Barrel, head, antenna, side stubs and feet come back from one 3/4 view; IoU to the
  bake 0.81–0.84 per diagonal (the body is a little wide). It is a rigid, symmetric machine, so the single view
  doesn't invent anything the other views disagree with, as the wolf's head did.
- **TRELLIS's texture is not.** It read light cel-shaded metal as dark reflective metal and baked it in blotches
  ([its texture](3d-render/stubby-trellis-texture.png)); one gamma (0.40) to the input's lightness doesn't save it.
  Same verdict as the props spike ("too smooth", "dark").
- **Projected paint on the TRELLIS shape reads as the stubby**: colours, band, antenna and goggle land. Where the
  shape is off, features double: the goggle strap shows twice in NE/NW, and its plate is a little low in SE.

So for machines: TRELLIS for shape only, paint by projection from a 4-view design (for a new machine, an NBP
2x2 sheet, as the wolf had). Next simple step: a rigid-part rig (body, head, two feet, antenna) and Materia's
procedural bob and waddle, which a machine needs instead of a clip library.

### The stubby, from a T-pose drawing, animated

Jin: don't reconstruct from the rendered sprite; have Codex draw the stubby in a T-pose, make the 3D from that,
animate it, and turn it back into game sprites. The whole loop, image to Materia atlas:

1. **Drawing.** `codex exec -i` with the bake's four diagonals and a prompt for the same robot in a T-pose (stubs
   straight out), a 3/4 front view, a clean toy render with soft even light on white. Codex's image generation
   kept every part (goggle and strap, antenna, band, chest plate, stubs, feet), one try.

   ![T-pose drawing](3d-render/stubby-tpose-drawing.png)

2. **Mesh.** TRELLIS.2 with texture, 75 s on gin. From a clean, evenly lit drawing the texture is usable this time
   (one gamma, 0.39, to the drawing's lightness), unlike from the cel-shaded sprite; the orange is a little muddy.
3. **Rig and animation**, `tools/render3d/animate_parts.py`, no rigging tool: the T-pose places the mesh (the stubs'
   line is the X axis), and the geometry cuts it into rigid parts: feet (bottom 8.5 %), stubs (outside the barrel at
   their height), head (above the narrowest slice between them and the antenna, blended over a centimetre). The
   stubs are lowered 70° from the T-pose, then everything moves by Materia's own stubby gait (`stubby.ts`): idle bob
   with a look round, a hopping waddle whose roll the head lags, stubs swinging, feet stepping. Front/back is the one
   thing the T-pose doesn't settle (`--flip`); here it came out right.

   Rest pose / the cut (head blue, stubs orange and yellow, feet green and purple), SE NE NW SW:

   ![parts](3d-render/stubby-tpose-parts.png)

4. **Sprites.** Same camera, lines and 4-direction strip as the rest of the spike. Walk (SE, NW), idle (SE, every
   4th frame):

   ![walk](3d-render/stubby-tpose-walk.gif)
   ![walk frames](3d-render/stubby-tpose-walk.png)
   ![idle frames](3d-render/stubby-tpose-idle.png)

`sprute check animation --directions 4` passes all 12 (clip × direction); the minimum over frames:

| | identity | facing | coverage |
|---|---|---|---|
| idle (36 frames) | 0.941–0.975 | −0.019 (the head turned away) – 0.041 | 0.939–0.981 |
| walk (8) | 0.939–0.956 | 0.020–0.057 | 0.957–0.976 |
| run (8, the walk at twice the rate) | 0.925–0.956 | 0.020–0.056 | 0.960–0.979 |

Identity is at SCAIL2's level (0.94–0.96), up from the wolf's 0.81–0.87: the reference is rendered from the same
mesh. Materia's `pack-atlas.py` packs idle/walk/run (at `--scale 0.75`: 36 frames × 256 px pass its 8192 px limit)
and `check-atlas.py` says ok. It stands taller in its cell than Materia's stubby (feet at 236 vs 223 of 256), which
`--height` or the packer's `heightBlocks` sets. Render: 2:38 for all 52 frames on a MacBook CPU.

**Secondary motion: the springy antenna.** The antenna is cut as one more part (what rises above the dome, from the
first slice narrower than a third of it) and rides on the head; its tip is Materia's `Dangle` (Verlet, pulled to
its rest place, a little weight), stepped at 120 Hz. Three changes from Materia's:

- The spring is softer, `--stiff 300` against Materia's 900: at 900 the walk bends it 4°, which doesn't show at
  256 px; at 300, 23° (walk). 120 gave 42° and looked loose.
- It bends from where the nub narrows to the rod, not from the dome: bending from the dome tilted the nub and
  opened a seam round it.
- A 40° stop: the run (the walk's steps at twice the rate) set it resonating to 80°; with the stop, 35°.

It is simulated for three loops before the recorded one, so every clip loops without a jump. Walk, head
enlarged (SE, NW):

![antenna](3d-render/stubby-tpose-antenna.png)
![run](3d-render/stubby-tpose-run.gif)

The checks above are with the antenna swinging (walk identity 0.939–0.956, run 0.925–0.956, all pass). The idle
hardly moves it (2°): the head's look round turns it about its own axis. The goggle strap has no loose tails in
this drawing, so it has no dangles.

What this shows: **for a machine, a T-pose drawing is enough** — no 4-view design, no projection, no rig. The pose
gives the placement and the parts; the motion, springs included, is a few lines of code per monster, as in Materia.
What it doesn't show yet: a body without obvious parts (the wolf).

### One command: a new machine from words

`tools/render3d/make_character.py` chains the three steps: Codex draws the T-pose (from `--prompt`, or redrawing a
`--reference` design), `trellis_shape.py --textured` makes the mesh on gin (behind any running workflow), and
`animate_parts.py` cuts, animates and renders it. Steps already done are kept, so a rerun resumes.

```bash
python tools/render3d/make_character.py out --name brassy --prompt "a brass diving-helmet robot: a round brass helmet head with one round glass porthole for a face showing a glowing teal eye, rivets, a copper barrel body with a pressure gauge on its chest, dark iron arms and boots"
```

The prompt says the look; the body plan (head with an antenna, barrel, two side stubs, two feet, T-pose, 3/4 front,
even light on white) is fixed in the script, because the cut and the gait are the stubby's. About 5 minutes: Codex
~1.5, TRELLIS 70 s, render ~2.5.

![brassy T-pose drawing](3d-render/brassy-tpose-drawing.png)
![brassy rest and cut](3d-render/brassy-rest-parts.png)
![brassy walk](3d-render/brassy-walk.gif)

The first try taught three things, now fixed:

- **Codex turned the head.** "Turned 30° to its left" turned the head further than the body, so TRELLIS built a helmet
  whose porthole looked sideways. The prompt now says head and body face the same way.
- **A head wider than the barrel lost bits to the stubs.** Four vertices of the helmet's side bolt lay past the
  barrel's edge, below the stubs' height cap, and were lowered with the arm: a thin spike from the helmet. Stubs now
  stop at the neck. The shoulders also blend across the barrel's edge (as the neck does), so a big shoulder bends
  instead of tearing when lowered.
- **A gap in the mesh** (a slice of the antenna with no vertices) crashed the cut; gaps now count as narrow.

The stubby renders as before with these changes. Brassy passes `sprute check animation --directions 4` on all 12
(minimum over frames), and Materia's `pack-atlas.py --scale 0.75` / `check-atlas.py` say ok (anchor [96, 180],
figureHeight 178):

| | identity | facing | coverage |
|---|---|---|---|
| idle (36) | 0.977–0.982 | 0.020–0.049 | 0.966–0.987 |
| walk (8) | 0.954–0.972 | 0.037–0.039 | 0.924–0.942 |
| run (8) | 0.939–0.968 | 0.038–0.047 | 0.942–0.961 |

## Costs and timings

| | 2D path (SCAIL2) | 3D path (this prototype) |
|---|---|---|
| Per clip, 4 directions | ~80 s on the RTX PRO 6000 per seed; gallop took 3 seeds | 2.9 s a frame on a MacBook CPU (walk 12 frames 35 s, idle 40 frames 2 min). GPU would be well under a second. |
| Retries | `--attempts`, by eye for ghost legs | none: same input, same pixels |
| Design | 3 NBP paint-overs (~$0.4) + BiRefNet | same |
| Per new clip | a GPU run | a CPU render |
| 8 directions from a 4-view design | a second SCAIL2 run | free: S/E/N/W are painted from their neighbours (`--directions 8`) |
| Next step (TRELLIS mesh) | — | +273 s on gin once per character, + weight transfer (seconds, Blender) |

## What it unlocks

- **No seed lottery.** Gallop's ghost legs are gone by construction; so are melts and facing flips. `--attempts`
  and the check become a sanity test, not a filter.
- **Exact direction consistency.** One surface, one colour; a mark on the left flank stays on the left flank.
- **Any body with a rig.** Big monsters (`--cell 512`), six legs, tails — whatever a rig moves. Fast motions are
  as cheap as slow ones.
- **8 directions from 4 paintings**, and later any angle or zoom.
- **Cheap clips.** A new motion is a CPU render; the GPU is needed only for the design.
- **Recolour and parts for free** later (Materia's parked paint-mask idea): the paint is a function of the
  surface, so a mask is one more channel.

## What it loses

- **The silhouette is the mesh's.** The design's mane and fluff outside the husky's surface are dropped; the head
  and ears are the husky's shape (IoU 0.93 to the design, design-only 400 px per cell). This is the main cost and
  the reason the next step is a mesh from the design.
- **Painted light is baked in.** A leg that swings keeps the light it was painted with. Fine at 256 px; it would
  show on a slow turn of a large part.
- **Unseen surfaces are guessed** (paw soles, under the belly, the inside of a mouth): they take the nearest paint.
- **No hallucinated life.** SCAIL2 adds fur that moves, breathing, small expression; a render moves only what
  the rig moves. Secondary motion needs bones or Materia's Verlet chains (`soft.ts`) ported.
- **Needs a rig per body type.** Humanoids have Template-kun; animals have Quaternius; anything else needs a mesh
  and a rig made — the step SCAIL2 doesn't need.
- **Design is tied to the rig's pose.** A free-hand reference (BYO character) can't be projected; it has to go
  through the paint-over step.

## Recommendation

**Go**, scoped to non-humanoid and large monsters, where SCAIL2 is weakest and rigs exist; humanoid characters
stay on SCAIL2, which adds life a rig doesn't have.

The step after the prototype, **TRELLIS.2 mesh from the design + weights transferred from the template rig**, was
tried the same day (below). Weight transfer works; a single-view mesh doesn't. So the first real step is now:

**Give the template mesh the design's silhouette instead of replacing it.** Push the husky's vertices out (or in)
along their normals until its four silhouettes match the design's, in the reference pose, by minimising the
silhouette mismatch the fit below already measures (differentiable silhouettes, or per-view distance fields). The
head, legs and rig stay the template's, so the paint and the weights land where they belong; the mane and fluff get
geometry. Target: IoU ≥ 0.97 to the design in every diagonal (0.93 now).

Until then the husky-mesh render is usable as is for monsters whose design hugs the rig.

After that, productise as `animate --use render` (move the projection into a `Sprute Render Painted Rig` node in
`custom_nodes/sprute`, with the IoU guard), and `create character --body rig.glb` for the paint-over.

Not recommended: porting Materia's code-modelled bake into Sprute. It's the right tool for a game that models its
monsters by hand, but Sprute's users bring images.
