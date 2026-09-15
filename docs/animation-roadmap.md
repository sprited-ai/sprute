# Sprute: a year toward usable eight-direction animation

Objective: build an open-source Sprute tool that creates eight-direction sprite
animations. Planning horizon: September 2026–September 2027. These are working
milestones, not claims of model capability or promises that quality is solved.

For a concise account of the latest implementation and validation, see
[current walking status](walking-progress.md). The sections below retain the
longer-term requirements and the history behind them.

The current tool integration is [199](../experiments/199-integrated-walk-command/README.md):
`sprute animate` connects standing-character output to eight-direction walking
generation, collection, background removal, packing and preview. Existing real
SCAIL jobs produced 256 transparent frames through this command. Recovery was
tested with downloads and local processing interrupted, and completed real
artifacts resumed with network access disabled. This is an unpublished development
feature. Server installation, broader character validation, motion quality and
edge quality remain requirements; successful orchestration does not close them.

Earlier Lily evidence (142–159): all eight wingless Lily single-reference baseline
videos are collected, with 520 contact frames and selected native reference pairs
reviewed. [158](../experiments/158-lily-eight-view-comparison/README.md) provides a
hash-verified eight-view comparison and original reference sheet. Directional
facing persists in the inspected samples, but shorts patterns, faces, exposed arms,
hair and bows are redrawn inconsistently. NW frame 60 has a localized gray shoe
extension. This is not yet a coherent, accepted eight-direction sprite set.

[146](../experiments/146-lily-extra-front/README.md) reduces E shorts patches by adding
the original S reference at seed 7, while alternating limb poses remain. This is a
partial appearance result, not a default. [159](../experiments/159-lily-rear-extra-front/README.md)
completed the same intervention against N baseline 149. All 65 contacts and nine
native pairs were reviewed: pale shorts patches soften but remain, rear facing and
alternating limb poses persist, and early frames introduce a bright warm background
and stronger contrast. No rear face was observed. This is not an accepted default;
see its assessment for evidence and the startup appearance regression.

147/156 now cover original known-alpha Lily images in all eight directions with
one model/source pair. Partial-alpha MAE ranges about 0.318–0.336; pale edges remain
on dark backgrounds. 148 separates RGB contamination from alpha error and exposes
background-dependent error cancellation. These static controls do not provide ground
truth for generated frames or establish temporal alpha quality.

The next quality checks must cover continuous motion, foot contact, directional
phase/scale and loop seams. Same-index comparison is not physical phase alignment;
the S motion-driver camera elevation differs from the other views. Improving
appearance conditioning must retain movement. Transparent edges remain a separate
unsolved requirement. Neither additional videos nor successful packaging alone
satisfy these checks or arbitrary-character usability.

Current evidence (093–136): SCAIL identity tests cover all eight directions on
the controlled robot, with no complete quality acceptance. Masking an
extra reference's upper body restores E/seed123 walking, but the same mask adds
a detached artifact in W; no universal default is accepted. Two E cycle
candidates were extracted, but playback, contact and loop quality remain
unapproved. Matting tests expose bright fringes, lost thin details and incorrectly
opaque translucent material. RGB correction and simple trimaps do not solve
these failures. Direct-RGBA audits have not found a verified, usable replacement
for the character-reference plus motion-driver path. TransAnimate describes
image/sketch controls, but an official release was not located (115).

116 S/N are collected and visually reviewed: both retain key cuff/boot colors
but shins turn pale; S also invents cyan head-side markings. S has independent
identity-error evidence; N's brightness-only diagnosis is qualified by141 below.
Neither is quality-accepted.117's four diagonals are completed and reviewed as candidates only.
118 assembles all eight single-reference seed7 outputs. 119's added charcoal-shin
sentence fails to remove the S/N defects. 120's grayscale driving video also
retains the pale shin and head-side markings; chroma removal is not a fix.
121 extracts32-frame diagnostic cycles for all eight views. 122 provides a
synchronized local reviewer whose browser controls were tested, but human
playback/gait/contact acceptance remains outstanding.

123 confirms official SCAIL-2 supports direct RGB driving videos; pose extraction
is optional. 124 exports exact wingless-rig joints, and125 renders a body-only
skeleton with paired masks using the official cylinder renderer. It preserves
projected joints but uses an adapted camera/depth representation and omits face
and hand details. 126 completed the controlled S seed7 comparison against116:
all65 contacts and five native comparisons reviewed. Pale shins and cyan
head-side marks persist despite changing the representation; no default adopted.
Motion is not wholly frozen, but playback/contact/loop quality is unaccepted.
Inspect journals/history for live state and assessments for reviewed evidence.
Keep the alpha negative controls as independent acceptance requirements. No
arbitrary-character or eight-direction quality claim is justified yet.

127's bounded mask-function comparisons match numerically;128 finds CLIP
preprocessing differences, but129's official-preprocessing ablation does not
remove the appearance failures.130–132 compare neutral and stepping references:
dark-shin retention improves at both tested seeds on S, while other defects
remain.133 shows rounded boots alone are not proof of deformation under rotation;
the isolated spikes at132 frame38 are a stronger temporal concern.

134 lowers CFG5 to3 at stepping seed123. All65 contact frames and nine native
comparisons were inspected: the frame38 spikes disappear, colors remain, and
foot poses alternate. Head pitch and boot orientation also change.135's
color-area ranking supports reduced discontinuity but is not a quality gate.
136 completed the same CFG change against131's seed7 baseline. All65 contacts
and nine native comparisons were reviewed: the head-side oval disappears in
selected samples and foot poses alternate, but boot-area diagnostics are mixed.
CFG3 remains a candidate for cross-direction tests, not an accepted setting.
No CFG default has changed. Continuous playback,
contact, loop, alpha, other directions and unseen characters remain unverified.

137 extends the CFG-only comparison to N using116's unchanged neutral reference.
The completed65-frame result and11 native comparisons retain pale shins at12/28:
lower guidance alone is not a common front/rear identity fix.138 supplies a
synchronized four-panel S comparison for seeds7/123 and CFG5/3; its creation is
not playback acceptance. Next isolate the reference-pose effect on N at fixed
CFG3, preserving an exact neutral baseline before rendering the intervention.

139 prepares that reference with a pixel-exact neutral baseline and fixed scale;
140 completes the reference-only comparison against137. All65 contacts and11
native comparisons retain visible shin brightness variation at12/28. This is
not yet a solved correction. Before attributing brightness to changed material,
bound legitimate pose/lighting effects with controlled rigid-shin renders.

141 supplies a counterexample to brightness-only rejection: the unchanged source
leg under fixed lighting becomes much brighter and develops horizontal bands
under rigid hip rotation. Median encoded luma shifts58.88 at0° to105.30 at25°.
Earlier shin-based material-drift claims are therefore unproven without matched
pose/surface evidence. This revises the diagnosis, not the quality acceptance:
generated motion, geometry, loops and alpha still need independent review.

142 transfers the CFG3 SCAIL settings to wingless Lily S. All65 contacts and
nine native reference/result pairs reviewed: recognizable hair/bow/clothing,
front facing and alternating foot poses, with face and pixel patterns redrawn.
Candidate only; playback, contact, loops and alpha remain unaccepted. Next test
matched E reference/driver to examine cross-view consistency beyond the robot.

143 completes Lily E: all65 contacts and nine native comparisons show retained
right-facing profile and alternating limbs, with redrawn shorts/shoes/face detail.
S/E remain candidates pending cross-view and temporal review.144 creates32 S
transparent frames from source32..63; RGB/timing are preserved, but dark-background
review shows light edge fringes. Alpha and loop quality remain unaccepted.

## Completion evidence

A release must let someone other than its authors start with their own character
and generate a usable eight-direction walking animation through the documented
Sprute workflow. It must preserve identity and intended facing, maintain plausible
anatomy and ground contact, produce usable transparent edges and loops, and export
consistent timing and frame metadata. Demonstrate it on several unseen characters,
including asymmetric clothing and pale or translucent details. One convincing
fairy demo, green software tests, or a successful model request is insufficient.

The source, setup, export format, and repeatable generation path must be public.
Document code, model, and motion-template licenses separately. A supported local
route must be tested with its actual hardware requirements; optional hosted
providers must disclose costs and not be silently required for a supposedly local
workflow. Do not redistribute reference clips without verified rights.

## Months 1–3: reliable motion reference and a reproducible baseline

- Obtain a natural side-view walk before expanding to eight synchronized views.
  The eight-cell wingless Lily test (012) failed: non-front views turned
  toward the camera. The isolated Lily profile (013) holds its facing in reviewed
  frames and has a 19-frame candidate cycle, but repeated playback, foot contact
  and the wrap still need review. Do not batch other directions yet. The earlier
  fairy comparison (011) remains unapproved.
- Test transfer of a reviewed reference into the correctly matched WAN workflow.
  Measure identity/facing/contact failures rather than counting changed pixels.
  Lily transfer (013) now exists: sampled facing holds, but motion differs at the
  same driver timestamps and style changes. Investigate temporal alignment before
  assuming shared driver timing will synchronize eight outputs. The loader-only
  and VAE-roundtrip controls (014) retain timing; generation/conditioning remains
  the unresolved boundary. Do not apply a blanket two-frame offset. Raising
  pose strength to 1.5 in the fixed test (015) did not resolve the discrepancy;
  retain 1.0 as the research baseline rather than assuming stronger is better.
  A second-character side transfer (016, Lily driver → Elias) retains recognizable
  target appearance in sampled frames. An isolated rear-facing Lily
  Seedance candidate (017) now holds its facing in sampled frames; cycle selection,
  cross-view phase alignment remain unverified. Rear transfer to Elias (018)
  holds facing but is rejected because an unrelated object appears late in the
  clip. Whole-clip review is required; early clean frames are insufficient. This is still
  far short of an eight-direction demonstration.
- Establish a small, explicitly licensed reference/template corpus with rejected
  examples retained as negative controls. Generated drivers remain labeled as such.
- Move frame layout and output handling from one-off scripts into Sprute. The
  offline atlas exporter and frame-by-frame video reviewer now exist. The reviewer
  retains every decoded frame, supports up to eight grid cells and exports notes.
  Matting integration, cross-view timing and generation quality remain unresolved.

## Months 4–6: repeatable eight-view generation

- Compare full-grid generation with per-view generation driven by shared timing.
  Test phase consistency and cross-view identity; preserve the user's preference
  for one synchronized generation wherever output quality supports it.
- Implement the chosen local provider in Sprute, with explicit model/node version
  pairing, resumable job IDs, bounded retries, and no duplicate paid submissions.
- Read-only ComfyUI recovery now retrieves an existing job’s video without
  resubmitting, including explicit running/queued/unknown states. Actual
  API-workflow submission now records a client UUID before POST and treats an
  existing journal exclusively as recovery. This requires a server that honors
  client prompt IDs. An integrated model/template provider and beginner-facing
  eight-view generation still remain to implement.
- Build quality comparisons across multiple characters and actions. Keep failures
  visible. Validate front, side, rear, and diagonal views independently.

## Months 7–9: usable game assets and external users

- Integrate per-cell alpha processing, loop selection, stable framing and anchors.
  Validate pale wings, hair, props, and asymmetric equipment without mirroring away
  the distinction between left and right.
- Test exports in a game engine and a small browser demo. Direction changes must
  retain phase and not jump between incompatible poses or scales.
- Have beginners use the documented workflow on their own drawings. Remove setup
  friction based on observed problems, not an assumption that terminal familiarity
  is universal. Make generation cost and hardware choices understandable.

## Months 10–12: reproducibility and release

- Freeze tested dependencies and supported model/template versions; verify fresh
  installation, cancellation/recovery, outputs and troubleshooting instructions.
- Publish source, examples with suitable rights, repeatable evaluation inputs and
  known limitations. Test the packaged CLI from a clean installation.
- Release only with actual multi-character eight-direction evidence. Keep the
  objective active if the animation quality or reproducibility remains unproven.

## Current decision

The current experimental baseline uses a licensed rigged walk rendered from
eight cameras, then transfers each matching view through WAN Animate 2. The
Seedance investigations below are retained as history and negative controls;
they are not the current motion-template recommendation. Experiments 040–048
established this baseline, 054 transferred it to Elias, and 062 has produced
all eight hat/dress views. These are known characters, not the unseen or
asymmetric-character evidence required for release.

The checkout can prepare eight character references, render/upload motion drivers,
plan workflows without editing node IDs, upload references, submit/recover batches,
review every decoded frame, extract candidate cycles, matte, register and pack
views, and export Godot SpriteFrames. These are separate development commands,
not yet a beginner-tested end-to-end workflow. Actual Godot checks cover pixels,
rectangles and timing; they do not establish natural walking or aligned gait.

The hat/dress atlas is recorded in064. More recent controlled asymmetric-robot
tests077–085 expose persistent hand geometry and part-color failures. Frontal
conditioning, explicit hand text, exposed-arm references and a late pose window
have not established a general fix.086 completed the gray versus blue motion-source
comparison in E/W seed7/123 pairs: hand defects persist and W-seed7 still changes
boot colors. None of these conditioning changes is promoted. Further work needs
persistent part identity through occlusion and exact source geometry, alongside
the remaining motion and usability gates.
See [identity findings](animation-identity-findings.md) for evidence and limits.

Same-host runtime installation/inference evidence exists in074/075;083 directly
installed the pinned dependency list and084 validated hash-enforced resolution
only. Another-machine setup, hardware requirements and the complete license audit
remain open. Keep persistent identity, ground contact, shared phase, seams,
transparent edges, unseen characters and beginner integration as release gates.
The published0.4.1 release still provides standing views only.

## Historical experiment log

The entries below preserve decisions and observations made during each experiment.
Past statements such as "running", "next" or "remaining" are historical snapshots,
not instructions to submit jobs again. Read the current decision above and inspect
the experiment's durable journals and server state before acting. Later completion
entries supersede earlier progress notes without erasing the original evidence.

### Upstream audit follow-up

See [provenance notes](animation-provenance.md) and
[checkpoint identity](animation-models.json). The installed distilled checkpoint
matches the publisher's SHA-256. Our six-step UniPC runs differ from the upstream
Euler/10 example. Compare that sampling configuration before further speculative
parameter sweeps, keeping source, target, seed and prompt fixed. Caption format
and viewpoint control are separate follow-ups. This does not erase the observed
failures or certify the alternate configuration.

Euler/10 comparison (019) is now complete: the rear transfer still generates
extraneous objects late in the clip. Keep it rejected. A smaller artifact-area
measurement is not a pass. Next isolate the recommended caption structure;
sampler/step changes alone did not remove the observed failure.

The recommended-style appearance caption test (020) also retains late foreign
objects and is rejected. The saved rear driver's left-quarter region is empty
across all 81 frames; verify the actual rear loader/conditioning path next rather
than continuing prompt tweaks. The exact defect remains unresolved.

Rear input audit (021) saved the actual loader and image-node outputs. The loaded
81-frame video's artifact region is empty and the target reference matches
exactly. No visible input contamination was found at those boundaries; internal
conditioning remains unchecked. Next test a directly generated short gait clip,
not a crop that conceals a failed long output, and review every frame plus its
loop connection before using it.

Direct 29-frame rear generation (022) avoids the large foreign objects in the
reviewed full short clip, but introduces pale background texture in its first
two frames and is not a verified loop. The zero left-quarter detector score
misses that texture. Keep it an unapproved candidate for alpha/loop work, not
proof of solved generation or an excuse to ignore whole-frame visual review.

Existing flood-fill keying applied to the complete short rear clip (023) removes
the pale background pattern on checkerboard review and preserves recognizable
hair/clothing/boots. All 29 RGBA frames and an alpha WebP are retained. This is a
single-character alpha candidate, not a seamless loop or evidence for translucent
characters; cycle selection and cross-view phase alignment remain required.

The offline review page now supports explicit inclusive repeat ranges, join
navigation and range metadata in downloaded notes. Full original frames remain
accessible. Browser checks covered range selection and stepping; the emitted
page-script integration check verifies exported indices/duration and invalid
range rejection. This provides the selection tool, not verified gait phases.

Shared rear-driver viewpoint test (024) generated a right-facing Elias but a
mostly vertical, unconvincing side gait. Keeping the same model and target while
switching to Lily's side motion and matching source conditioning (025) restores
clear forward/back foot extension. Direction-matched motion is the current
baseline. All 29 frames were reviewed; torso rotation, initial background texture,
and an unapproved loop remain. Side and rear templates have different cycle
lengths (19 versus 26 frames); explicit gait-phase alignment remains necessary
before eight-direction assembly. See experiments 024 and 025 for retained output
and comparison evidence.

Source phase candidate (026) maps observed opposing strides in E/N to a shared
24-frame cycle, retaining all source indices and labeling anatomical identity as
an inference. Fixed registration (027) then matches cycle-median alpha bounds to
a common scale and foot baseline without per-frame recentering. All 48 registered
frames retain canvas margins; bottom medians both equal 436. Dark checkerboard
review exposes bright fringes and source foot shadows. These remain unapproved
two-view source candidates; neither output phase alignment nor eight-direction
readiness is established.

Edge-color probe (028) preserves all 48 alpha planes while attempting to remove
background RGB from partial pixels. Enlarged crops still show fringe, including
in opaque-only diagnostics; source RGB confirms a retained side foot shadow.
The simple correction is rejected as a sufficient fix and is not a new default.
Matte estimation and source shadow separation remain unresolved.

Existing local ToonOut applied to all 48 original phase-mapped RGB frames (029)
removes the inspected side-view shadow and trapped inter-leg background while
retaining recognizable white shoes. All phases were inspected as contact sheets;
fine-edge temporal stability remains unproven. Five repeated-input pairs have
identical alpha planes. Use this as the next experimental matting baseline;
some edge contamination persists and production defaults are unchanged.

Aligned E/N sources were passed through Animate2 (030): opposing steps transfer,
but repeated input phases do not reproduce output poses exactly. A25-frame
start-conditioning comparison (031) does not close the loop. A separate official
WAN2.2 I2V first/last-frame route (032) runs locally with installed weights, but its
short25-frame Lily candidate changes style/proportions and produces leaping
strides mid-clip; reject it as a template. No endpoint-only pass or seamless-loop
claim is justified. The official longer temporal configuration remains untested
for this specific candidate.

The81-frame,16fps follow-up (033) removes the pronounced leaping/style conversion
observed in the25-frame first/last run. It generates multiple walking-like cycles
despite a one-cycle prompt. All81 frames were reviewed; a native13-frame side
cycle is retained as an unapproved candidate. This establishes a promising local
motion-source branch, not an accepted loop. Next check another direction before
assuming it generalizes, and verify transfer and output timing separately.

Rear-view local first/last generation (034) maintains rear facing across all81
reviewed frames with alternating feet. Some startup blur and appearance changes
remain. An11-frame native rear cycle is retained as unapproved; the side candidate
has13 frames, so they are not aligned. S andNE standing inputs are prepared for
testing additional directions, not counted as animation results.

S/NE trials (035) completed with162 frames reviewed. S mostly sways and is rejected
as a walking template. NE keeps general rear-right facing but has angle changes
and pronounced lifted-leg poses; it is not approved as a natural walk. Standing
endpoints differ from the earlier stride inputs, so their influence needs an
isolated test. The development CLI now exports inclusive cycle selections with
original PNG bytes and per-frame timing;51 tests/build pass and a real13-frame
export matches every reviewed source file. No animation template is approved by
that export operation.

Explicit rear-to-front Animate2 motion transfer (036) produces alternating
forward-looking foot extensions while retaining a frontal Lily appearance,
improving on035's sway. All25 frames were reviewed and an11-frame native range
was exported through the CLI. This is an unapproved candidate: anatomical phase,
contact, matte and loop join remain unchecked. Rear-to-front viewpoint transfer
must not be generalized to all directions; the earlier rear-to-side test lacked
a convincing side stride.

Rear-source NE/SE transfer (037) completes50 reviewed frames but produces bodies
and feet that read predominantly as rear/front views, with only the head keeping
more diagonal orientation. Reject both as sufficient diagonal walks. Next compare
a real diagonal motion source with the target/settings fixed; do not extrapolate
rear-to-front success to a single-driver solution for all eight directions.

Direction-matched NE source conditioning (038) restores a clearer diagonal torso
and oblique leg movement compared with037's rear-driver result. All25 frames were
reviewed. The source's high knee lifts and angle variation persist; it remains
unapproved. The comparison changes source video plus its matching vision/caption
conditioning and does not establish shared gait phase or a seamless loop.

Remaining-view experiment (039) submits separate SE/W/NW/SW local first/last
jobs from the existing wingless Lily directional stills. SE has completed with
all81 frames inspected: alternating oblique steps but torso-angle oscillation and
standing-like pauses persist. A20-frame native range is retained unapproved;
other jobs are still pending review. These are independently generated videos,
not proof that the original sheet contains independently authored left views.

Experiment039 is now complete: all324 native frames were inspected. W retains
left-facing alternating fore/aft steps and an11-frame candidate; local ToonOut
retains its white sneakers, but edge stability remains unapproved. NW is rejected
as a natural walk due to lifted/airborne-looking poses and irregular-looking
mid-clip rhythm. SW retains broad front-left facing but has pauses and angle
oscillation. Eight usable synchronized animations are still absent.

Experiment040 begins a licensed rigged-motion control: Quaternius's CC0 Standard
archive from the creator's OpenGameArt upload includes a mannequin and Walk_Loop.
Bundled license confirms CC0; the archive hash is retained. One action can be
rendered from eight cameras on the same timeline, avoiding independent source
cycle durations. This tests input consistency; it does not prove WAN transfer,
Lily identity, output phase, or natural target anatomy. The downloaded archive is
not established as the latest itch release, so newer release fixes are not assumed.

Rigged-source rendering (040) now retains all256 frames across eight cameras.
The32-frame source cycle uses24fps; all pose-bone matrices at source0/32 match
exactly. All directional contact sheets were inspected. W/NW transfer (041)
completed with all66 native frames reviewed. Both retain Lily and broad facing;
NW avoids039's pronounced leaps. Generated endpoints still differ from their
beginnings and foot overlap/angle variation persists. Input phase equality has
not proved output phase equality. Two-cycle65-frame follow-ups (042) are submitted
to inspect internal repetition, with whole-clip review required before selecting
any interior range. No loop or eight-direction release is approved.

Two-cycle test042 completed with all130 native frames inspected. Both W/NW have
minimum tested RGB recurrence difference at32frames and close broad poses at an
interior4–35 loop join. Original32-frame candidate ranges are retained without
interpolation; foot overlap, appearance variation and anatomical phase remain
unapproved. Experiment043 submits the remaining six directions using the same
33-frame rigged-source baseline as041 so evaluation expands to all eight views.
It must not be confused with the longer interior-cycle candidates from042.

All six043 jobs have completed, with all198 native frames inspected. Combined
with041 W/NW, the first fixed-rig-source eight-view Lily baseline now exists:
264 inspected frames and a33-frame24fps comparison with native order preserved.
S has weak frontal foot motion; diagonal head/torso changes, output seams, contact,
matting and cross-view anatomical phase remain unresolved. This is an actual
eight-view generation comparison, not an approved game asset or end-user release.
Source job IDs, hashes and assembly method are retained. Next isolate frontal
projection/readability before promoting the baseline into a reusable template.

Frontal projection comparison044 changes only the source camera elevation from
approximately14.93 to30 degrees, with all recorded source bone coordinates equal
across32 samples. The matching vision image changes with the video; target,
caption, timing and sampler remain fixed. All33 output frames were reviewed.
Enlarged foot comparisons show more visible alternating shoe separation and knee
bends while frontal Lily appearance remains. This is an unapproved candidate,
not a contact or loop pass.045 submits the same30-degree source for65-frame
repetition to seek an interior32-frame frontal candidate.


Frontal two-cycle045 is reviewed across all65 frames. A32-frame native4–35
candidate retains alternating shoes and frontal identity; its recurrence diagnostic
is lowest at32frames, but shoe/appearance changes persist at the inspected join.
046 now has32-frame transparent S/W/NW candidates, all inspected at128px. Enlarged
S crops retain pale edge fringe despite keeping white sneakers and inter-leg gaps.
These are unapproved loops.048 has submitted the remaining SE/E/NE/N/SW65-frame
runs via the durable CLI; all job journals are retained. Full output review, phase,
contact and game-sized eight-view assembly remain outstanding.


048 SE/E have completed with all130 native frames reviewed. Both retain broad
facing and alternating strides; each native4–35 range is retained as a32-frame
candidate. Both have minimum tested RGB recurrence at lag32, and close broad
poses in enlarged35→4 joins, but changing shoe shapes, torso angles and passing
foot overlap remain.046 adds32 transparent SE frames and a four-view S/SE/W/NW
comparison at identical indices without phase adjustment. This exposes candidates
for comparison; equal frame counts do not certify anatomical phase. NE is running,
N/SW queued at the latest server check. E matting remains pending.


The shared exporter now accepts separate per-direction PNG arrays through views,
removing the manual grid-composition step. All8 views, equal frame counts and exact
geometry are required; no mirroring or timing correction is inferred.58 tests and
build pass.049 packs real040 control renders and verifies all256 RGBA crops and
frame durations.046 E now adds32 reviewed small transparent candidate frames.
This is export and matte progress, not proof of usable8-direction generation.


All048 outputs have now completed; NE/N/SW add195 inspected native frames,
completing the eight longer-output clips across042/045/048. Each direction has a
32-frame4–35 candidate, with original65-frame clips retained.046 completes all256
transparent candidate frames, each inspected at128px.050 packs these actual Lily
frames through the separate-view CLI into a4096×1024 RGBA atlas and verifies every
one of256 decoded crops plus frame durations. Its eight-view WebP comes from the
atlas itself. This is the first complete transparent eight-direction candidate
atlas in this branch, not a release-quality pass. Shoe geometry, body-angle
variation, dark-background fringe, anatomical phase, ground contact and unseen
character validation remain open. Next evaluate direction switching and gait
phase in an interactive player before calling the asset usable.


050 now includes a self-contained interactive atlas player. Browser checks verify
same-frame direction changes across8 buttons,0/31 wrapping, keyboard selection,
playback and auto-switching. Framing measurements expose an unresolved defect:
at128px S median silhouette height/bottom96/115 differs from SE89/108 and E89/109.
The current atlas is not registered consistently across directions. Next compare
fixed per-direction registration while preserving cycle motion, then assess
anatomical phase and foot contact separately. The candidate remains unapproved.

051 compares fixed registration on all8 generated views using native512px matte
inputs and one scale/translation per direction. Output cycle-median height/bottom
are90/109px for all directions, reducing050's7px spread. Within-cycle bottom ranges
remain106–112px; all256 alpha extents stay on canvas and packed crops match inputs.
Before/after sample grids and the registered browser player were inspected. This
is a framing correction candidate, not anatomical phase/contact validation. Next
trace foot identity and shared source phases before approving direction switching.

052 projects named source L/R foot bones through the exact cameras and compares
four source/target phases across all8 views. S/N pale-shoe centroid diagnostics
suggest+2-frame lag against source foot midpoints, but varying the source landmark
changes estimates to0–3frames. Mask samples were inspected and identify shoe pixels,
yet these are not tracked anatomical joints. A universal2-frame correction is not
supported and no frames were shifted. Next obtain comparable target foot/ankle
annotations with uncertainty before timing edits; all8 phase/contact approval is
still outstanding.

053 moves fixed registration into the shared browser-safe registerAnimationView
core function and optional views-manifest registration for pack-animation. All256
native Lily frames run through the CLI; per-direction transforms equal051 and all
RGBA output matches an independent oracle of the explicit pixel-center sampling
rule. Pillow boundary sampling differs in N and is documented, not hidden.61 tests
and build pass. Background removal, joint/phase validation and a beginner-ready
character-to-animation generation path remain outstanding.

054 begins the second-character comparison under the fixed-rig65-frame baseline:
Elias references replace Lily in all8 directions, changing only target image,
appearance caption and filename prefix. Motion, source vision/caption, sampler
and timing are unchanged. All8 references and remote file availability were
checked; durable CLI journals retain the8 submitted jobs. This is a previously
used character, not unseen-character validation. Whole-clip review must inspect
brown boots/tunic/curls and appearance leakage; Lily's pale-shoe metric does not
apply unchanged. No candidate range or quality pass is assumed in advance.

055 moves local independent-frame ToonOut processing into matte-animation for
single-view extracted cycles. It preserves source indices, durations and hashes,
preflights paths/geometry, refuses overwrite and removes partial outputs on failure.
Two actual model frames reproduce046 RGBA exactly;62 tests/build pass. Temporal
edge quality and restartable per-frame processing remain unresolved.054 S has
completed with all65 frames reviewed: recognizable Elias, alternating boots and
no visible Lily accessory leakage; loop/contact/matte approval remains pending.
054 SE is downloaded but unreviewed, E running and the other5 views queued.


054 now has all eight completed videos, with every native frame inspected
(520 total). NE/N/NW/W/SW add 325 reviewed frames. Every direction retains a
4–35 candidate after whole-clip and native join inspection. Tested RGB recurrence
is lowest at 32 in every view, but is only a diagnostic. Elias remains recognizable
without visible wings, Lily accessories or large foreign objects. Passing boots
overlap and hair/tunic/hand silhouettes vary; contact and loop quality are unapproved.
S/SE/E local mattes are complete and all 96 small checkerboard frames were inspected.
The five other directions still need matting. An unregistered eight-view candidate
WebP now permits direct comparison; framing and directional phase remain unresolved. This remains
a known-character comparison, not unseen-character validation or release approval.

054 NE matting completed and all 32 small checkerboard frames were inspected.
Brown boots and blonde hair remain visible, with boot overlap and silhouette
changes still present. N/NW/W/SW are being processed sequentially by the same
local CLI batch (session 41538; verify the live handle before resuming).
056 prepares the real eight-view matte inputs for production registration and
packing, records input hashes and refuses incomplete direction sets. Its missing
cycle guard has been exercised; full atlas execution awaits the remaining mattes.

054 N matting completed; all 32 small checkerboard frames were inspected, with
both boots and blonde hair retained. Five directions now have reviewed small
matte previews (160 frames). NW is running in session 41538, followed by W/SW.
056 adds an independent RGBA sampling and atlas metadata verifier plus a preview
of exported cells. Only syntax is checked until all input mattes finish.

054 NW matting completed and all 32 small checkerboard frames were inspected.
Native frames 12 and 28 were also composited onto dark and light backgrounds.
A thin pale fringe is visible around portions of hair, hands, tunic and boots
on dark backgrounds. This is concrete edge-quality evidence, not a release pass.
W is processing in the existing session 41538; SW follows. Six directions now
have reviewed small matte previews (192 frames).

054 W has now completed too: all 32 small checkerboard frames inspected.
Seven directions have reviewed small matte previews (224 frames). Only SW
remains, running in the existing batch session 41538. Atlas output is pending.

054 all eight mattes are now complete; all 256 small checkerboard frames were
inspected. Session 41538 exited successfully. 056 packed all 256 real Elias
frames through the production registration CLI and independently verified every
RGBA cell against its hashed native source under the recorded transform. All
metadata rectangles/durations matched. Median bottom is 109 px in all views;
median height is 90 px except NE 89.5 px. Exported phases 0/16 were visually
inspected and a full animated comparison saved. The embedded player exists but
awaits browser interaction review. Edge fringes, boot overlap, contact, phase and
loop quality remain unresolved; this is not unseen-character validation.

056 browser review completed for direction controls, forward/backward wrap,
background selection and advancing playback with half-speed/auto-switch options.
All eight buttons retained frame 24. Enlarged dark S24/NW31 still show pale
fringes; light SE5 was also inspected. UI correctness does not establish contact
or anatomical phase agreement. The next image-quality experiment should compare
edge treatments against these observed fringes while preserving thin details.

057 compares four edge treatments on Elias NW12/28 and pale-shoed Lily S12/28.
All sixteen dark-background previews were inspected. Nearest-interior color
borrowing reduces some pale fringes while preserving alpha; a wider band alters
opaque outlines too. Alpha erosion removes 1,170–1,310 nonzero pixels per sample.
No default changed: four stills cannot establish temporal stability, true color
or thin-feature preservation. Full-cycle dark/light comparison is next.

058 extends both color treatments across two full cycles (64 originals, 128
modified frames), preserving every alpha byte. All 64 wider-treatment small
frames and selected dark/light samples were inspected. Largest fixed-coordinate
correction changes selected Elias 6→7 and Lily 18→19 for native inspection;
movement confounds this diagnostic, so it is not a flicker score. Wider borrowing
reduces fringes but changes opaque contour colors. No production default changed.
Known-foreground thin-outline validation is needed before integration.

059 known-foreground tests reject nearest-interior color borrowing as a default:
both variants increased dark-composite error for all three synthetic cases.
The wide variant visibly replaced a pink outline with blue interior color.
Known-alpha background unmixing nearly recovers this synthetic truth, but a
0.15 partial-coverage bias raises error strongly, especially for pale features.
This does not establish real model alpha bias or validate unmixing for WAN frames.
Keep original matte output as the baseline; no production default changed.

060 adds a real Godot integration example. Official 4.7.2 macOS binary checksum
verified; engine tests passed for 256 RGBA texture crops, durations, all eight
frame/progress-preserving direction changes, playback advance and loop signal.
OpenGL compatibility GPU capture of NW frame 12 was inspected. No manual keyboard
event test or complete engine motion-quality review yet. This closes an initial
engine compatibility gap, not contact, edge, phase or beginner-workflow quality.

061 moves Godot resource generation into the export-godot CLI. It validates
packed metadata/geometry, preserves PNG bytes and explicit durations, refuses
overwrite and exports portable SpriteFrames plus import settings. Initial default
Godot import altered RGB in 11,305 nonzero-alpha pixels; disabling alpha-border
correction via exported settings made all 256 actual engine crop hashes match.
All track names, durations and loop flags passed. 64 tests and build pass.
This is checkout-only; animation-quality gates remain unresolved.

062 begins an additional hat-and-dress character walking comparison using
examples/blue-dress.spritesheet.png. This image was used in 009 image tests, so
it is not fully unseen or asymmetric validation. Eight references were inspected
and 24 server input paths checked. Same rigged baseline; only target image,
appearance caption and output prefix changed. All eight durable jobs submitted;
S verified running, the remaining seven queued. Whole-clip quality review pending.

063 adds actual-engine coverage beyond the original uniform loop fixture:
three frames per direction, fps 10, explicit 100/250/150 ms durations and loop
false. All 24 RGBA crop hashes matched; all eight tracks emitted finished and
remained stopped on frame 2. Resource durations matched; sub-frame wall-clock
precision is not claimed. 062's existing S job was verified running this turn,
with seven queued; no generation job was restarted.

062 S completed. All 65 native frames and the 35/4/36 join were inspected.
Hat/blue band, floral dress and gray shoes remain recognizable with alternating
shoe extension; hat/hem contours and dress texture vary. A native 4–35 candidate
was extracted after review; recurrence minimum at 32 is diagnostic only. Local
ToonOut processing started in session 17595. SE verified running, six queued.
Contact, seam and matte quality remain unapproved.

062 SE completed and all 65 native frames plus join were inspected. Hat/dress/
gray-shoe appearance remains recognizable, with passing-shoe overlap and changing
hat, face and hem contours. Native 4–35 candidate extracted; SE local matting
is running in session 16740. S matting finished and all 32 small checkerboard
frames were inspected; hat brim, dress and shoes remain visible. E verified
running, NE/N/NW/W/SW queued. No contact or loop-quality approval.

062 E/NE add 130 reviewed native frames, including native join inspection.
Hat/dress/shoes remain recognizable; hem lifts, texture changes and passing-shoe
overlap remain. Both native 4–35 candidates extracted. SE matting completed
and all 32 small checkerboard frames were inspected. E then NE are processing
sequentially in session 7043. N verified running; NW/W/SW queued. Four original
clips (260 frames) and two matte cycles (64 frames) reviewed; no quality pass.

062 N adds 65 reviewed native frames and the 35/4/36 join comparison.
Rear hat/dress/shoes remain recognizable with local hair, hem and texture
variation. Native 4–35 candidate extracted. E and NE matting completed;
all 64 small checkerboard frames inspected. Total five original clips
(325 frames) and four matte cycles (128 frames) reviewed. Contact, phase,
native edge quality and loop seams remain unapproved.

062 all eight generation jobs completed and were collected without resubmission.
NW/W/SW add 195 reviewed native frames and three native 35/4/36 join
comparisons. All 520 native frames have now been inspected as contact sheets.
All eight native 4–35 candidates extracted; RGB recurrence minimum is 32
for these last three views, but this is not a contact/phase/loop-quality pass.
Left-side shoe contours, passing overlap, hem and texture variation remain.
N matting is live in local session 51080; remaining NW/W/SW mattes pending.

N matting subsequently completed; all 32 small checkerboard frames inspected.
Five matte cycles (160 frames) now reviewed. NW then W then SW matting
started sequentially in local session 95229. No new generation submissions.

062 NW matting completed and all 32 small checkerboard frames inspected.
Six matte cycles (192 frames) reviewed. W is now processing in the same
local session 95229, followed by SW. Experiment 064 preparation/verification
and player scripts are ready; preparation correctly refused the three missing
cycles when first checked. No atlas has yet been exported in 064. The roadmap
current decision now reflects the rigged matched-view baseline rather than
the older Seedance experiments.

062 all eight matte cycles completed; all 256 small checkerboard frames
inspected. Session 95229 exited successfully. Experiment 064 now packs all
eight views into 128px cells with fixed per-view transforms. All 256 atlas
crops match independent NumPy sampling of hashed RGBA inputs; metadata
rectangles and durations checked. Preparation also verifies each source time
and duration against 24fps within timestamp precision. Phase 0 and 16 contact
grids inspected. Eight-view WebP and self-contained player generated; animated
playback and browser interaction are not yet reviewed. No quality approval.

065 moves standing-sheet reference preparation into the checkout CLI:
prepare-animation writes eight independently cropped/resized/composited PNGs
and hashed character.json, with explicit fixed WAN framing and no upload or
generation. All eight real hat/dress outputs match the actual 062 reference
RGB pixels exactly. Tests cover distinct per-cell appearance, alpha composition,
placement, existing-output refusal and empty/opaque input rejection. All 66
tests in 13 files and build/DTS pass. Integrated driver/model setup, captions
and workflow construction still remain. The 064 browser review could not run
because CUA reported the Mac locked; player interaction remains unreviewed.

066 adds offline plan-animation to build all eight fixed local WAN graphs
from prepared character references, an appearance description and an explicit
eight-view driver manifest. It verifies/copies reference PNGs, writes portable
input subfolders and hashed workflows, and never submits. All eight real plans
differ from 062 only at target image, appearance caption and output prefix.
The new caption wrapper is not generation-tested. All 67 tests in 14 files and
build/DTS pass. Server preflight, automatic upload/submission/recovery and
portable licensed driver setup remain before a beginner-facing end-to-end path.

066 W caption comparison submitted once as job
70b1083e-27e8-4721-be04-dda9941033ba using the durable W-job.json journal.
Server queue confirmed running. All required node types and named model files
were listed; matching driver paths exist and remote reference SHA256 matches.
This is a presence/input audit, not a full dependency/license preflight. The
new appearance wrapper is the changed inference input relative to 062 W.
Only W submitted; seven remaining plans still unsubmitted. GET-only collector
script saved; generation and quality result pending.

check-animation-server now inspects the 14 node types and four model names
for the fixed planner profile using only GET requests. Real gin checking exposed
VHS encoder fields nested under selected format; support and a test fixture
were added. The final gin name/input check passes. It is explicitly not a
model-hash, asset-path, memory, full schema-value or quality certification.
All 68 tests in 15 files and build/DTS pass.

066 W generation completed and all 65 native frames were inspected. Broad
left facing and hat/dress identity remain recognizable; passing-shoe and hem
changes persist. RGB comparison with 062 W shows every frame differs (mean
absolute RGB difference 2.3104 on the 0–255 scale), not a quality ranking. One
known-character view supports planner execution, not general caption quality
or release readiness. Remaining seven generated plans still unsubmitted.

067 adds upload-animation for prepared plan inputs: validate all local hashes,
paths and geometry, inspect all remote names, upload missing images without
overwrite, and verify bytes by GET. No prompt submission or driver upload.
The test covers lost upload response recovery, exact input reuse, conflicts and
local tampering before network calls. All 69 tests in 16 files and build/DTS
pass. On actual gin, eight new Elias inputs uploaded and read-back verified;
a second run reused all eight. Existing hat/dress inputs also reused. No jobs
submitted in 067; automatic batch submission and portable drivers remain.

068 adds submit-animation-plan with immutable hashed workflow snapshots,
exclusive per-direction attempt records, and the existing durable job journals.
Recovery never POSTs attempted directions; unattempted directions can proceed.
Unknown/failed states stop the batch. Missing journal after an attempt is
ambiguous and never automatically retried. Tests cover a lost response, source
plan removal, subsequent recovery, missing journal and server mismatch. A macOS
path-alias false rejection was fixed using the canonical run directory. All
70 tests in 17 files and build/DTS pass. Actual gin accepted eight Elias jobs;
repeating the command recovered all eight without new submissions (S running,
seven queued). First-submit/recovery evidence saved in 068. Output quality
and batch video collection remain pending.

collect-animation-run now reads batch journals and downloads completed views
into run/results/D without POSTs. Reuse validates job identity, video length and
SHA256 and does not require server history. The shared single-job collector now
writes a streaming video hash. Tests cover partial completion, later downloads,
no-network reuse and same-length tampering. All 71 tests in 18 files and build/DTS
pass. Actual 068 S downloaded, then reused successfully; review-animation decoded
all 65 frames, not yet visually inspected. SE running, six remaining queued.
No new generation submissions.

068 S and SE now have all 130 native contact frames and native join
comparisons reviewed. S additionally compared to 054 at native9/25: broad
appearance and step posture similar, with local boot and texture variation.
Both native4–35 candidates extracted. S local matting running session2719;
SE matting not started. E downloaded and review contact sheets prepared but
not yet visually reviewed. NE last confirmed running; N/NW/W/SW queued.
No contact, anatomical phase or loop-quality approval.

068 E all65 native frames plus35/4/36 join reviewed; candidate4–35
extracted. Total three native clips (195frames) reviewed. S matting completed
and all32 small checkerboard frames inspected. SE then E matting started in
local session25836. NE now collected but unreviewed; N running and NW/W/SW
queued. No release-quality, foot-contact or loop approval.

068 NE/N add130 reviewed native frames plus join comparisons; both4–35
candidates extracted. Five native clips (325frames) now reviewed. SE matting
completed and all32 small checkerboard frames inspected; E is processing in
existing session25836. NE/N matting not yet started. NW last confirmed running,
W/SW queued. No contact, seam or native-edge quality approval.

068 NW adds65 reviewed native frames and the join comparison; 4–35
candidate extracted. Six native clips (390frames) now reviewed. E matting
completed and all32 small checkerboard frames inspected, for three matte
cycles (96frames). NE then N then NW matting started in session49244 after
session25836 ended successfully. W last confirmed running and SW queued.
No quality approval.

068 W collected and all65 native frames plus35/4/36 join inspected.
Candidate4–35 extracted. Seven native clips (455frames) reviewed; SW last
confirmed running. Local NE/N/NW matting remains active in session49244
(last observed NE10/32); W matting not started. No new jobs submitted.

068 SW all65 contact frames and native35/4/36 join reviewed; candidate4–35
extracted. All eight clips (520frames) now reviewed. NE/N/NW matte outputs
completed and all96 additional small checkerboard frames inspected, bringing
the matte review total to192frames across six views. W then SW matting
started in local session45792. SW recurrence minimum32 is diagnostic only;
hair and clothing differ between restart4 and natural-next36. No contact,
phase, seam, native-edge or release-quality approval.

## Cycle-folder packaging and completed batch068 matte review

All eight068 matte cycles completed; all256 small checkerboard frames reviewed.
Production pack-animation now accepts eight cycle folders directly, removing
the need to manually enumerate PNGs. It retains source indices, frame order and
explicit variable durations, checks matching timelines, and supports the existing
fixed framing. Conflicting input modes and escaping cycle frame paths are rejected.
72 tests /19 files and build/DTS passed.

069 packages the real068 batch through this path: all256 RGBA crops and durations
passed independent checks; phase0/16 grids viewed and Godot resource exported.
No engine review of069 yet. Motion/contact/phase/seam/native-edge approval remains
outstanding. Portable licensed driver/model setup and a beginner end-to-end flow
remain necessary; reducing packing input is one step, not completion.

## Portable licensed motion renderer

motion/render-walk-drivers.py now accepts an explicit pinned GLB, output folder
and optional FFmpeg executable. It renders the tested040/044 camera profile
without experiment-path dependencies, saves32 source PNGs and65-frame/24fps
videos for all8 views, paired first images/captions, hashes, source bones and CC0
license. It refuses other model hashes, existing destinations and nonclosing
source poses. A fresh070 Blender5.1.2 run passed all256 exactRGBA baseline
comparisons, first-frame pairs, video metadata/hash and bone-coordinate checks.
Existing-output refusal was exercised. No WAN run with this bundle yet; automatic
server installation/path mapping and fresh model setup remain outstanding.

## Motion upload and server driver mapping

Production upload-animation-drivers uploads16 hash-checked070 media assets via
ComfyUI, reuses matching content-derived names, refuses conflicts/renames and
creates a plan-compatible drivers.json using an explicit server input directory.
No prompt submissions. The command cannot discover/verify that absolute directory
and checks MP4 header rather than decoded motion. Unit recovery/conflict/path
tests pass; total73tests/20files, build/DTS passed.

071 actualgin:16uploaded, then16reused; independentSSH checks all media paths/hashes
and decoded65frames/24fps, plus all8 generated workflow paths/captions. No WAN
job submitted with the new bundle. Model installation, beginner orchestration,
unseen/asymmetric character evaluation and motion-quality improvements remain.

## Foot landmarks with explicit uncertainty

The earlier052 signal depended on shoe pixels and source landmark choice, so no
universal frame offset is justified. Review-animation now supports optional
reviewer-supplied ankle/toe positions with clear/uncertain/not-visible states,
frame/cell identity and original image coordinates. Tested emitted page mapping
under display scaling/cell offsets, null occluded points and frame-specific
clearing;73tests/20files and build/DTS pass.072 creates fresh068 E/N pages.
Native browser validation remains pending (Mac locked). Direct E/N native12
inspection finds covered ankle joints and overlapping E boots; no numerical
phase correction or motion-quality approval follows.

## Four-model and runtime inventory

073 full-file hashes match publisher immutable revisions for all four model
files, totaling41,043,835,715bytes. docs/animation-models.json and
animation-runtime.md record downloads, sizes, hashes, ComfyUI0.33.1 commit,
VideoHelperSuite1.7.9 package-file hashes and Python dependency versions.
The package has no own Git checkout; parent Comfy commit was not accepted as
its revision. Fresh tinyCUDA operation succeeds, while NVML fails due to
595.91 userspace/595.84 loaded-kernel mismatch. No driver changes/reboot.
Exact package artifact, clean isolated installation/fullWAN execution, measured
minimumhardware and auxiliary/matting/transitive notices remain outstanding.

## Isolated runtime install and actual inference

074 matches all45 installed VHS files to official1.7.9 registry archive
ac63991d8b237afe5b2cd2b287a14b4a4d40ff203c0f2ee9d5fe61059f57cdf8.
A separate clean ComfyUI checkout and fresh Pythonvenv installed104 dependencies
under observed constraints; pip check and14node/4modelname preflight pass.
Code/package pins and resolved artifact hashes are retained in docs/runtime locks.
Isolatedgin8190 server PID1330437; local18190 tunnel session77669.

075 submitted onlyS job2d7baa37-d6e1-4825-ae71-c7993288a6d2 and completed in
91.21seconds. All65 contact frames reviewed: front/appearance retained with
hair/clothing variation, no quality approval. Same GPU/OS and shared verified
weights; not a new-machine/minimum-hardware demonstration. Original idle server
cache was released through /free; no process stopped or drivers changed.
Derived requirements direct-install, remaining directions, unseen/asymmetric
characters, motion/contact/seams and beginner orchestration remain outstanding.

## New asymmetric controlled character

076 authors an original wingless primitive robot with red anatomical-left cuff,
blue left boot, yellow right boot, cyan front and dark rear panel. Eight independent
Blender views (no mirrored references) were reviewed and prepared with the CLI.
This is a new procedural control, not proof of arbitrary user-drawing support.
077 submits all8 directions once on the isolated074 runtime with installed070
drivers. Recovery confirms same IDs/no new submissions. Whole-frame visual and
fixed-color observations will assess recoloring/swaps/occlusion without treating
color presence or projected centers as anatomical ground truth.

077 S completes the first new-asymmetry check: all65 contact frames inspected.
Red cuff/blue boot stay viewer-right, yellow boot viewer-left in the frontal
sequence. RGB centroid ordering agrees across65frames; no color dropout.
Boot geometry and shin appearance vary, with pale surfaces on originally dark
legs. Contact/seams and remaining7directions remain unapproved/pending.

077 SE/E add130 reviewed frames (195total). SE passing blue boot becomes
wedge-like; E exposes a pale finger-like hand contrary to dark block source
hands and is rejected for identity detail. OriginalE hides the red cuff; red
absence is not independently treated as a proven loss. S/SE candidates4–35
extracted; session14437 mattesS thenSE. S32smallcheckerframes reviewed.
Next investigate conditioning of surfaces hidden in a direction reference;
no blanket phase or color correction is justified by these observations.


### 077–078 follow-up: hidden hand identity

All eight 077 videos are now collected without resubmission; review is still incomplete. N all65frames and native35/4/36 join were reviewed: rear markings persist, but contact/phase/seam remain unapproved. An initial late-cuff-loss suspicion was disproved by native-frame inspection and pixel counts. Experiment078 changes only appearance text (plus filename prefix): explicit dark fingerless block hands still produce a pale finger-like far hand in E, confirmed against baseline native16. Do not ship this caption as a fix. Evidence and limits: `experiments/078-block-hand-caption/assessment.json`. Next: finish remaining view reviews and test explicit hidden-surface conditioning, rather than assuming multi-image batches work; current node uses `reference_image[:1]`.


### 079: separate frontal CLIP appearance, side VAE reference

077 contact review now covers all520frames. E and W are rejected for identity defects; six other directions remain unapproved. S/SE32-frame matte contact reviews are complete, without native-edge acceptance.

079 E/W jobs completed with only target CLIP changed to frontal S (side VAE reference and pose branch fixed). All130frames reviewed on sheets and selected native comparisons inspected. E hidden hand darkens, but exact block shape and red far cuff are not recovered. W duplicated red cuff and blurred pale boot persist. No default changed. Further work needs spatial reference conditioning or view-consistent representation, with ground-contact/phase and beginner workflow requirements still open. Evidence: experiments/079-frontal-clip-appearance/README.md and per-view assessments.


### 080: frontal spatial reference

Complement to079, changing only WanAnimate2ToVideo reference_image to frontal S while preserving side CLIP/motion. E complete: all65frames reviewed; native8 confirms both boots blue where one should be yellow, with invented cyan side-head detail and changed body design. Rejected. W submitted once under job9650bd51-da74-4b18-8d6d-4022f6de57a7, last confirmed running; recover with experiments/080-frontal-vae-reference/collect-review.py. No default or release changed.


080 W completed: all65contactframes plus0/16/33/48 comparisons and15/47native crossings reviewed. One cuff improves but both boots become blue and side-head details are invented. Both080directions rejected; no pending080jobs. Consolidated evidence and next-design constraints: docs/animation-identity-findings.md.


081 completed both original jobs;130contactframes plus selected native comparisons reviewed. Same-side arms-exposed reference improves E cuff/hand colors and removes W cuff duplication in these frames; W15 boot blur improved. E hand remains fist-like. No defaults changed; next paired-seed validation077vs081 and exact-hand geometry work. Evidence: experiments/081-visible-side-arms/README.md.


082 paired reference-pose validation submitted once: seeds7/123 × E/W ×077baseline/081posed =8jobs. Within-pair graph differences verified limited to reference filename/output prefix; durable journals match frozen workflow hashes. First confirmed running, seven queued. Recover with experiments/082-reference-pose-seeds/collect.py (exit2pending); prepare-review.py decodes and builds all-frame/same-index pairs. Criteria fixed before generation; no cherry-picking or quality claim from submission.


083 direct derived requirements install started in new /home/gin/dev/sprute-repro-083/venv, original SSHsession26027. Large NVIDIA wheels downloading, not complete at last inspection. Existing074server and082jobs preserved. Inspect original handle/log/result before continuing; never rerun merely on timeout. 082 E-seed7-baseline collected/all65contact+native16reviewed: dark hand but pale far cuff; paired posed comparison pending.


083 direct requirements installation completed144.28s, pipcheckpasses;104/104 versions, artifact hashes and URLs match recorded runtime/python-artifacts.json, requirements SHA matches. No other-machine or083inference claim. 082 E-seed7pair reviewed130frames+0/16/33/48native: posed reference restores red far cuff, dark hands in both, finger-like detail remains; comparison assessment saved. Remaining6jobs under original journals.

082 is now fully collected and paired review is complete. All eight frozen
workflow hashes and collected video hashes were verified, with65 decoded frames
per job. Seed123 E improves early boot hue preservation; W removes duplicated
red cuff. Both retain invented hand detail. W-seed7 posed boot recoloring remains
a negative case. No default promotion or quality approval. Next identity work
must address persistent part colors and hand geometry together, and repeat this
complete comparison rather than select a favorable seed. Contact/phase/seams,
independent characters, alpha edges and beginner integration remain separate
requirements. Assessments: `experiments/082-reference-pose-seeds/assessment.json`.

084 pip hash-enforced resolution dry run completed:104 exact wheel versions,
URLs and SHA256 hashes match the inventory. This is not a hash-enforced fresh
installation; same-host caches were used. Another-machine verification remains
open.

### 085: motion condition window (running)

Four jobs compare082 posed references at E/W × seeds7/123 against a single
change: pose_end_percent1→0.7. Frozen graphs and durable journals live in
`experiments/085-pose-window`; recover with its collect.py, never resubmit after
an observation timeout. The installed node accepts RGB motion video, so raw
mannequin video is not itself a schema mismatch. Appearance leakage remains a
hypothesis. CPU schedule calculation shows an inclusive overlap at step7 and
complement-only conditions at steps8–9; do not describe this as exactly three
pose-free steps. Evaluate hand/part colors and motion regressions together before
any default decision. No output quality claim yet.


085 completed all four jobs and260 contact-frame reviews, with selected native
comparisons. No exact-hand recovery; W-seed7 teal/reddish boot defects persist.
All workflow/video hashes verified; no default promotion and no pending085jobs.

086 neutral motion source rendered all eight views with identical source bone
JSON and matching camera/timing metadata to070. Gray motion RGB/first image/text
replace the blue motion appearance together; this is not single-channel isolation.
All16 uploaded media hashes verified. Four E/W seed7/123 jobs are submitted once
under experiments/086-neutral-motion-source; collect.py recovers their journals.
No086 output quality claim yet. This tests source appearance, not another pose
window value; reference, sampler and full pose window remain082 defaults.


086 completed all four original jobs,260 contact-frame reviews and selected
native comparisons. Gray appearance changes wrong boot hues without restoring
blue at W-seed7 16/54; sampled hand defects persist in both seeds. All workflow
and collected video hashes verified; three newer review folders additionally
verify65 PNG hashes each. No default promotion or pending086jobs.

087 added source/per-PNG SHA256 provenance to review-animation and downloaded
notes, with a before/after source-content check around decoding. Three relevant
FFmpeg/cycle tests and build/DTS passed; actual086 W-seed7 review verified65 frame
hashes. Existing reviews are not retroactively certified, and hashes do not imply
animation quality or enforce browser file integrity. No npm release.

088 verified an alternative multi-reference input path: the installed SCAIL-2
node encodes each reference independently and keeps matched identity-mask data.
A CPU recording-VAE probe retained two distinct reference latents and passed
shape assertions. This is node wiring evidence, not neural inference or proof of
downstream model use. Official documentation also cautions that extra references
can degrade quality. Next prepare verified primary/additional/driver masks and
audit model availability, then compare side-only versus side+front with fixed
SCAIL settings and durable jobs. Keep007's style-loss result as a regression.
Details and primary sources: `experiments/088-scail-multireference-audit/README.md`.

089 prepared the wingless robot's E/W/S reference images and six SCAIL identity
masks. Source alpha uses the same crop, placement and nearest sampling as existing
RGB references; all normalized RGB pixels matched and all mask PNGs roundtripped.
E/W primary and S extra silhouettes were visually inspected. One blue identity is
shared across directions, with white primary and black additional backgrounds.
This completes reference-mask preparation only; motion masks, checkpoint provenance,
real model input validation and paired inference remain. See
`experiments/089-scail-reference-masks/README.md` and its verification.json.

090 completed geometry-derived motion masks for all eight 070 directions using
transparent rendering with unchanged rig/cameras/timing. Source bones are byte-identical;
opaque RGB comparison has only sparse channel differences of at most 1, not exact
identity. All 520 FFV1 mask frames decode to their expected exact RGB hashes.
Sixteen silhouette samples were visually inspected. Reference and driver masks now
exist locally; checkpoint provenance, Comfy decoder/model input checks and paired
SCAIL inference remain. No generation submitted. See
`experiments/090-scail-motion-masks/README.md`.

091 verified the full existing SCAIL checkpoint SHA256 against Comfy-Org's pinned
publisher LFS pointer. The installed VHS CPU video loader also returned all130
E/W mask frames exactly equal to their source float RGB, preserving colors/order.
An initial standalone import issue was resolved by initializing server/queue
objects without starting a listener or submitting prompts. Real VAE/model input
validation and paired inference remain; no weights downloaded or defaults changed.
See `experiments/091-scail-checkpoint-provenance/README.md`.

092 ran actual GPU VAE encoding and installed SCAIL conditioning on both E/W
references plus front, 65-frame drivers and identity masks. Separate reference
latents remained distinct and finite; pose/reference/driver mask shapes passed.
VAE, driver, mask and copied reference hashes match the prior verified artifacts.
Text conditioning was a placeholder and no diffusion model was loaded or sampled.
Actual SCAIL model consumption and paired generation remain. See
`experiments/092-scail-real-vae/README.md`.

093 prepared all eight SCAIL side-only/side-front paired workflows, with exact
within-pair differences verified. The verified fp8 checkpoint is linked into074.
First E-seed7 side job 0142ec5c-bee7-4483-ae0c-f093fbc27460 is sampling, and
E-seed7 side-front b3867b14-f6c4-4dc2-a312-dc39b9940f6f is queued at this log entry.
Six others are prepared but not submitted. Server log confirms actual WAN21_SCAIL2
loading and sampler progress. Settings are40 UniPC/simple steps, CFG5, shift3,
no LoRA. GET-only collect.py checks journal/workflow hashes and does not restart.
No output quality has been reviewed yet; consult live history for current state.
See `experiments/093-scail-paired-generation/README.md`.

093 follow-up: E-seed7-side completed; all65 contact frames and native16/48 reviewed.
Hands look block-like and boots retain blue/yellow, but invented yellow shoulder
and colored torso details prevent acceptance. Side-front is sampling successfully;
the remaining six prespecified jobs are now journaled and queued. No jobs restarted.
prepare-review.mjs verifies source/PNG hashes and produces full-frame contacts plus
fixed native paired comparisons. No default promotion or loop/contact acceptance.

093 recurrence follow-up: first output has lower pixel error at32-frame lag than
between adjacent frames, but first wrap31→0 differs more than original31→32.
Native seam grid inspected and documented; still no seamless-loop/contact claim.
Side-front remains actively sampling at this entry, with six jobs queued.

093 first pair now reviewed: E-seed7 side-front completed, all65 contact frames and
native paired0/16/48/64 inspected. Front addition turns the far red cuff gray at16/48,
retains yellow neck artifacts, and introduces early background/contrast differences.
Reject multi-reference promotion for this pair. E-seed123-side is running and five
jobs queued at this entry. Six remaining outcomes must still be reviewed.

094 preserves review provenance through extract-cycle: selected recorded hashes
and staged copies are checked; output carries review/video and per-frame hashes.
Legacy reviews remain supported without retroactive certification. Four relevant
tests plus build/DTS passed;32 real093 extracted frames byte-matched their review.
Diagnostic extraction only, not loop acceptance.093 generation continues unchanged.

093 E-seed123-side completed:65 contact frames and native16/48 reviewed. Red far
cuff/dark block hands retained; seed7's yellow neck patch is not obvious in these
samples. Cyan chest geometry and motion/contact remain unresolved. Candidate only.
Same-seed side-front is running, four W jobs queued. No new jobs or defaults.

095 source occlusion check: original076 robot rendered with081 arm swing signs
reversed and unchanged cameras/geometry. E reveals a thin cyan front chest stripe.
Cyan visibility in093 E-seed123 alone is not an invented-part failure; exact shape
matching remains unverified. Both static source renders inspected and source/camera
hash data recorded. No generated inputs or queued jobs changed.

093 both E pairs reviewed: seed123 side-front has two yellow boots across contacts,
confirmed at native0/16/48/64, versus blue/yellow side-only. Red cuff stays red,
unlike seed7. Early brightness/contrast discontinuity recurs. Both E seeds reject
extra-front promotion for distinct color regressions. W-seed7-side now running;
three W jobs queued. No W or complete eight-direction quality conclusion.

093 W-seed7-side completed and reviewed:65 contacts plus native0/16/33/54.
No obvious red cuff duplication or blue/yellow boot replacement, but yellow
rear-neck patch and irregular far-arm outline remain. Side-front is running;
two W-seed123 jobs queued. No pair/default/loop acceptance yet.

093 W-seed7 pair reviewed: extra front retains cuff/boot colors but changes arm
pose/swing and keeps an olive rear-neck artifact. Both outputs unaccepted. Last
W-seed123 pair is running/queued. Six outputs now reviewed,390 contact frames plus
selected native pairs. No overall default or gait/contact/loop acceptance.

093 W-seed123-side now reviewed:65 contacts and native0/16/33/54. Cuff/boot colors
retained, no obvious yellow neck patch in samples; irregular occluded far-arm edge
at16 prevents exact-geometry acceptance. Seven outputs reviewed; only final
W-seed123-side-front job remains running. No restarts or new tests submitted.

093 finished: all8 jobs complete, all520 contacts plus specified native frames
reviewed, all workflow/video/frame hashes verified. Last W-seed123 side-front
retains colors but adds early warm/bright appearance; occluded geometry unresolved.
No extra-reference default promotion. Keep side-only experimental baseline and
address occluded-part identity/geometry; contact, full8directions, loops, alpha,
arbitrary characters and beginner release remain open. No093 jobs pending.

096 DPO follow-up: E/W seed7 complete,130 contact frames plus native comparisons
reviewed. E changes stride without removing invented yellow neck detail; W turns
the blue boot yellow near the end. Reject default promotion and defer remaining
seed123 candidates. No jobs pending. Related q-create training reports also
record identity failures for existing sprite adapters; those are different tasks,
not robot measurements (see096/related-training.md). Next work should improve
reference/occlusion representation and measure identity separately from motion,
instead of assuming generic detail correction or reconstruction loss solves both.
