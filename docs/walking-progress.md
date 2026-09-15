# Walking development status — September 14, 2026

Sprute's development version connects an eight-view standing character to a
walking sprite sheet, a browser preview and a Godot export. **Walking is still
unpublished and its visual quality is experimental.** npm0.4.1 makes standing
views. For instructions, use [set up walking](walking-setup.md), then
[make a walk](walking.md).

## Current snapshot

The experimental One-to-All runner now reuses a model across eight directions.
One measured batch took 315.75 seconds versus 498.74 seconds for the earlier
isolated-process run, with all 520 PNGs identical. This excludes matting and export
and does not improve the underlying gait. The option remains experimental and is
not the backend used by the integrated `animate` command.

The development packing and `animate` commands also support `--hold-frames 2`
to show fewer drawings while preserving the cycle's duration. Saved walks retain
their selected setting on resume. Godot loaded all eight exported tracks with
the expected timings. This is a timing choice, not automatic anime key-pose selection.

See [local animation, timings and memory](local-animation.md) for current setup
boundaries and measurements, and [walking instructions](walking.md) for usage.

## Model experiment history

An isolated One-to-All 1.3B experiment recovered the hat character’s face and
chibi proportions in the E view by using reference head landmarks relative to
the moving neck. That result survived two seeds ([289](../experiments/289-reference-head-conditioning/README.md),
[290](../experiments/290-reference-head-second-seed/README.md)). Applying the same
treatment to N failed: the hat acquired face-like marks and the feet deformed
([291](../experiments/291-rear-reference-head/README.md)). Omitting invisible head
landmarks in the N reference and driving poses removed those artifacts in one
paired trial, but the hat brim still changed ([292](../experiments/292-rear-hidden-landmarks/README.md)).
This is an experimental conditioning lead, not an accepted eight-direction backend. The public package
and current development defaults have not changed. Robot pose detection, hidden
landmarks, contact, loop continuity and alpha quality remain unresolved.

The front-view trial exposed a separate problem: the upstream anchor-based leg
scaling lengthened the legs. Estimating lengths across the cycle restored chibi
proportions, but the generated walk became nearly stationary. Pose/image guidance
changes and explicit walking text did not rescue it ([295](../experiments/295-front-retarget-ratios/README.md),
[296](../experiments/296-cycle-leg-ratios/README.md), [303](../experiments/303-front-walk-prompt/README.md)).
Decoded motion and learned control signals are present; this remains an unresolved
motion-following problem, not a usable front-view walk.

A diagnostic mannequin with an enlarged head and shortened body did produce
visible alternating steps when reference and driving body poses came directly
from its known 3D rig ([309](../experiments/309-rig-driven-proportion-pair/README.md)).
The unmodified mannequin also walked under the same pose policy. This shows that
short proportions do not invariably prevent motion in this runtime; it does not
solve the actual hat-and-dress case. Both controls omit facial and hand landmarks,
and their input pipeline differs from the hat experiments. A geometry audit also
found the pose detector's inferred nose and eyes below the enlarged mannequin
head despite passing core confidence thresholds ([308](../experiments/308-rig-projected-chibi-pose/README.md)).
Adding an opaque skirt to that same chibi reference preserved visible foot
alternation while all other conditioning files remained byte-identical
([310](../experiments/310-chibi-skirt-occlusion/README.md)). These front-view,
single-seed controls narrow the investigation; the next requirement is transferring
the known-pose approach to the actual character, not accepting mannequin gait as
the finished feature.

The first transfer back to the actual hat character recovered clear alternating
steps in the front view ([311](../experiments/311-hat-rig-motion/README.md)). It fits
the rig motion to reference shoulder width and a projected ankle envelope, with
reference head landmarks following the neck. Appearance is broadly recognizable,
but the high knee lift and skirt deformation look like marching. Ordinary gait,
precise identity and eight-direction consistency remain unapproved.

Scaling only knee/ankle vertical excursions to75% retained visible stepping with
less knee exposure in two seeds ([313](../experiments/313-hat-three-quarter-lift/README.md),
[314](../experiments/314-hat-lift-second-seed/README.md)). Reducing them to50% made
the feet nearly stationary ([312](../experiments/312-hat-half-lift/README.md)).
The75% result is a front-view candidate, with remaining clothing/shoe variation
and no continuous playback or eight-direction quality approval.

The first rear-view transfer also retained alternating steps and a broad hat brim
([315](../experiments/315-hat-rear-rig-motion/README.md)), using rear-projected rig
poses and no invisible face landmarks. Arm positions and hair/dress contours still
change. Side-view fitting and consistency across all eight views remain unverified.

The first side-view rig transfer was rejected: profile shoulder-width fitting
would expand motion22-fold, and a uniform vertical-envelope fallback still
produced oversized strides and skirt deformation ([316](../experiments/316-hat-side-rig-fit/README.md)).
View-specific stride handling remains necessary; the newer pipeline has not
replaced the earlier side candidate.
Follow-up changes reduced stride and forward lean but did not establish a better
ordinary side walk; matching the estimated hip position added no clear improvement
([317](../experiments/317-side-half-stride/README.md),
[319](../experiments/319-side-torso-rotation/README.md),
[320](../experiments/320-side-hip-placement/README.md)). These remain diagnostic
experiments, not general retargeting defaults.

The first SE diagonal trial retained broad diagonal facing and alternating legs,
but inherited oversized strides and skirt lifting ([321](../experiments/321-hat-front-diagonal/README.md)).
Direction coverage is expanding; a consistent ordinary gait across the views is
still not established.

NE also retained rear-diagonal facing and a hat brim, but elongated legs and
oversized gait prevent acceptance ([322](../experiments/322-hat-rear-diagonal/README.md)).
The current known-rig line has generated S, SE, E, NE and N; W, SW and NW are
untested in this line. None of this establishes an approved eight-direction set.
The repeated side/diagonal distortion points to shared template fitting as the
next investigation, rather than promoting accumulated per-view adjustments.

A shared template audit found that uniform shrinking is undone by diagonal
shoulder-width fitting. Reducing world-space depth while keeping width instead
reduces diagonal stride ([323](../experiments/323-eight-view-template-audit/README.md)).
Its first SE generation retained stepping with less stride and skirt lifting
([324](../experiments/324-se-compact-depth/README.md)); other views and repeatability
of this candidate remain to be checked.
The same depth adjustment also reduced NE stride while retaining stepping and
rear-diagonal facing ([325](../experiments/325-ne-compact-depth/README.md)).
This provides two-direction evidence for the shared preparation change; clothing
variation, remaining views, repeatability and export quality still need validation.

The shared conditioning module reproduces24 saved body cases and both SE/NE
rendered input sets exactly ([326](../experiments/326-rig-conditioning-module/README.md)).
Its first W generation retained left-facing steps but changed body proportions,
hat tilt and arm pose ([327](../experiments/327-western-views/README.md)).
SW and NW have now also completed, with 65 PNG frames verified for each.
SW retains diagonal stepping with appearance variation. NW fails appearance
review: the hat brim disappears and hair and dress change substantially.
The [eight-direction reviewer](../experiments/328-eight-direction-review/preview.html)
collects these mixed candidates beside their original references. Its playback
controls passed a headless Chrome check; this is not visual gait approval or a
release-quality eight-direction set.

An [alignment audit](../experiments/329-reference-rig-alignment-audit/README.md)
finds shoulder-angle and hip-height differences in NW, but comparable differences
also occur in the better NE candidate. This does not isolate the cause of NW
hat loss. Side-view projected shoulder lines are nearly degenerate, so their
angles must not be used as automatic quality thresholds.

A [second NW seed](../experiments/330-nw-second-seed/README.md) with all 69 input
hashes unchanged also fails: the hat disappears and an invented face appears
despite the rear reference. Both inspected seeds lose identity. Stop seed
selection for this configuration and investigate rear head/facing conditioning
without reintroducing the incorrect facial landmarks on the hat.

An explicit rear-facing appearance [caption](../experiments/331-nw-facing-caption/README.md)
substantially improves NW in a matched seed-42 run: inspected phases retain hat
brim, ribbon, short proportions and stepping. All 69 conditioning files and other
run settings match the failed baseline. Some rotation toward the rear remains.
The [seed-123 repeat](../experiments/332-nw-caption-second-seed/README.md) also
retains the hat, short proportions and stepping in inspected frames, unlike its
matched empty-prompt baseline. This provides two-seed evidence for the caption;
continuous gait/export acceptance and general reliability remain unproven.
The [revised mixed reviewer](../experiments/333-eight-direction-caption-review/preview.html)
uses the captioned NW candidate and retains the other seven candidates. W remains
unaccepted, and NW still rotates toward rear during the cycle.

The same [caption strategy on W](../experiments/334-w-facing-caption/README.md)
improves hat angle and proportions somewhat in a matched seed, but forward arm
reach persists. The input right wrist already stays much closer vertically to
its shoulder than the static reference landmarks. Inspect source arm geometry
before more wording changes; this input measurement is not causal proof or
anatomical ground truth. The W reviewer candidate remains unaccepted.

A [3D source audit](../experiments/335-source-arm-geometry/README.md) finds similar
elbow flexion in both arms. The W camera's 30-degree elevation projects their
lateral displacement into opposite vertical offsets (about -11.8px and +11.9px
on average). This reconstructs the saved wrist offsets within 0.00004px and
explains the input asymmetry, not the entire generated artifact. Inspect camera
elevation and shared arm abduction before applying a one-sided 2D correction.

A [shared half-abduction experiment](../experiments/336-half-arm-abduction/README.md)
rigidly rotates each elbow/wrist pair toward the body in world coordinates,
preserving pre-scale arm lengths and every non-arm joint in all eight projected
views. In a matched captioned W run, inspected phases show less forward reach
with stepping retained. Some held-forward hand posture and appearance changes
remain. Validate another view before promoting this single-seed improvement.

The [SE cross-view check](../experiments/337-se-half-arm-abduction/README.md)
also brings the arms nearer the body while retaining stepping and recognizable
face/hat in inspected phases. It changes only elbow/wrist trajectories against
324, with reference inputs and other run settings fixed. This supports the shared
arm transform in W and SE on this character; other characters, repeatability and
continuous gait/contact/export acceptance remain outstanding.

The [reusable arm module](../experiments/338-arm-geometry-module/README.md) now
drives experiment336 preparation. Five checks cover geometric invariants, invalid
inputs and exact eight-view coordinate/W-SE metadata parity. Regeneration also
preserves artifact hashes. This removes duplicated preparation logic without
changing model output or promoting the transform to the public backend.

The [Elias reference audit](../experiments/339-elias-reference-poses/README.md)
adds a second character for evaluation. All eight views have high core landmark
coverage, but N has overlapping lower-body points and facial landmarks on hair.
It is rejected as an automatic reference pose despite the scores. SE is a
candidate for a matched arm-transform trial; no new animation quality claim is
made. Robot automatic-pose failure remains unresolved.

The [Elias SE matched pair](../experiments/340-elias-arm-pair/README.md) completed
both original-arm and half-abduction runs with identical reference and sampling
settings. Inspected phases retain stepping and recognizable identity in both;
the adjusted arms stay somewhat nearer the torso. This modest second-character
benefit supports the experimental option, while facing and appearance variation,
robot/N reference failures and continuous gait/export acceptance remain unresolved.

A [common preparation command](../experiments/341-preparation-command/README.md)
now accepts reviewed reference metadata and projected motion with explicit fit
and head policies. It records input/output hashes, refuses existing outputs and
reproduces saved SE metadata. Four checks pass, including a real CLI invocation.
This is experimental metadata preparation, not the public generation workflow.

The [common conditioning renderer](../experiments/342-common-conditioning-renderer/README.md)
now consumes fitted metadata and a reference PNG. Real SE/NW command runs reproduce
all 138 prior conditioning files exactly across visible/hidden head policies,
including encoded videos. Pinned renderer sources and input shapes are checked.
This completes a reusable preparation-to-cache step, not model orchestration,
fresh installation or acceptance of the failed NW animation used as a fixture.

The [common generation command](../experiments/343-common-generation-command/README.md)
now consumes the renderer output on the configured GPU server. A real SE run
reproduces all 65 experiment337 PNGs exactly; output hashes verify, and reuse of
the completed output path exits before loading a model. Input validation has four
additional checks. This connects one experimental generation, not eight-job
orchestration, the public service, fresh installation or new visual acceptance.

An [eight-direction runner](../experiments/344-eight-direction-runner/README.md)
now validates all inputs before sequential dispatch and stops on failure. Four
simulated-child contract tests pass, and real validation covers eight configured
caches. Legacy E metadata was adapted in a copy after video/hash verification.
No full eight-job GPU run has yet tested this new runner; quality, public-service
integration and output export remain separate requirements.

The [real eight-direction batch](../experiments/345-real-eight-direction-batch/README.md)
has started. Its first observed completed direction, S, verifies all files and
matches all 65 prior PNGs. The parent and SE child were confirmed live at that
snapshot. This is partial progress; recheck the active process before treating
the remaining directions as complete or starting another batch.

That same batch subsequently exited successfully: all eight directions completed,
528 output files verified and all 520 PNGs match their prior individual runs.
The [actual batch preview](../experiments/346-batch-review-command/preview/preview.html)
was built from those outputs and passed a headless Chrome playback/control check.
This closes the configured-host batch/review execution check. It does not approve
appearance, facing, continuous gait, foot contact, transparent export or fresh setup.

The [batch cycle bridge](../experiments/347-batch-cycle-export/README.md) extracts
256 original PNGs (32..63 per direction) into the existing Sprute cycle format.
The TypeScript cycle reader accepts all eight folders, and hashes, source indices
and timing verify. These remain RGB cycles; existing matting and atlas export
can now consume them but have not yet been exercised on this batch.

The [real ToonOut batch](../experiments/348-batch-transparent-cycles/README.md)
has started through the existing matting function. Its first completed S cycle
preserves all 32 source RGB frames and timestamps with verified provenance.
Dark/white phase panels retain the main silhouette but show a thin light fringe
on dark backgrounds. Other directions were still processing at this snapshot;
full completion and temporal alpha quality remain unproven.

That matting run subsequently exited successfully and all 256 transparent frames
verify original RGB, source indices/timing and pinned model/runtime provenance.
The [actual atlas preview](../experiments/349-batch-game-export/preview.html) and
[Godot project](../experiments/349-batch-game-export/godot-demo/project.godot) now
exist. The 4096×1024 RGBA atlas contains eight 32-frame tracks at 128px; browser
controls and the real Godot interaction harness passed. This connects the actual
experimental batch through matting, packing and engine export. Light fringing,
appearance/facing consistency, continuous gait and fresh beginner setup remain
unresolved; loop playback enabled is not seamless-loop acceptance.

The read-only [edge audit](../experiments/350-alpha-edge-audit/README.md) measured
all 256 source-resolution transparent frames. Depending on direction, 10.7–14.3%
of partial-alpha pixels resemble the sampled border background color. The mask
application retains original RGB, so edge color contamination remains a plausible
contributor. This is not a ground-truth alpha error measurement; no mask erosion,
RGB correction, or product default has been applied.

A [controlled RGB correction experiment](../experiments/351-edge-color-correction/README.md)
then tested known synthetic colors/alpha plus unchanged-alpha candidates for all
256 actual frames. Exact-background unmixing worked on the synthetic fixture,
but background error could make full correction worse. A tapered candidate left
visible pale outlines in the directly inspected S/W views, so this remains a
diagnostic experiment rather than a default or a claimed fringe fix.

## What works in the development version

- Generate and collect eight direction videos, remove their backgrounds and
  export32 frames per direction. A real full run completed using the separately
  installed server runtime in [236](../experiments/236-installer-eight-direction-walk/README.md).
- Resume saved jobs and completed local stages. Ctrl+C now finishes the current
  processing pass, releases its lock and prints a resume command. Separate CLI
  processes passed actual macOS signal checks in [254](../experiments/254-native-cli-stop/README.md).
- Compare the selected walking direction with its original standing picture,
  change the background and save or reload frame-specific review notes. The latest
  [comparison preview](../experiments/263-reload-review-notes/preview.html)
  shows Elias; source/atlas bytes are retained unchanged. Actual Chrome file-input
  checks passed in [264](../experiments/264-browser-review-notes/README.md).
- Export a Godot4 project with arrow-key movement in eight directions. The
  [installed-package check](../experiments/242-installed-development-package/README.md)
  includes engine checks. This does not establish that the generated gait looks good.

The current source passed104 tests across28 files and an isolated build in
[258](../experiments/258-integrated-preview-check/verification.json). A build or
test count is not a visual quality score or a public release.

The latest preview and interruption features also passed a private installed
package check in [262](../experiments/262-installed-preview-recovery/README.md):
all35 packed files matched the installation, native CLI interruption/resume
kept the same jobs, and the preview embedded the exact original and atlas bytes.
This reused the same Mac and dependency cache; npm publication remains pending.

## What still prevents a general quality claim

Generated faces, clothing, hands and shoes can change. The hat-and-dress checks
show that anchoring the first source frame can help visible appearance, but it
can also create skin artifacts. Repeating five source frames reduced those
artifacts in one front-view test; the matched side-view test did not establish
a clear overall improvement. These settings remain experiments, not defaults.
See [251](../experiments/251-five-frame-source-anchor/README.md) and
[252](../experiments/252-side-five-frame-anchor/README.md).

The current [robot comparison](../experiments/257-robot-source-anchor/README.md)
tests that idea on an asymmetric character. Its baseline has hand/forearm
deformation and an added yellow neck/chest patch in inspected frames. The paired
anchor preserves more of the standing silhouette but largely suppresses the
walking poses across its65-frame contact sheet. That is a failed walking result,
so the anchor will not become the general default. A single follow-up doubling
pose strength also failed to restore walking; that strength sweep is stopped
([260](../experiments/260-robot-anchor-pose-strength/README.md)).

Natural walking, foot contact, transitions between directions, seamless loops
and transparent edges still need acceptance across characters. Matching frame
timestamps does not prove matching foot phases. Thin details and translucent
materials remain difficult. The standing generator also mirrors some views,
which can put asymmetric accessories on the wrong side before animation starts.

Setup still requires technical help with a Linux GPU server and large models.
Same-host runtime and package checks have succeeded, but this is not yet a
validated beginner setup on a fresh second machine.

A follow-up using an extra front upper-body reference instead of a temporal
anchor retained movement, but only showed local arm-contour changes without
clear overall source restoration ([261](../experiments/261-upper-front-reference/README.md)).
It also remains outside the default pipeline.

## Next decisions

Reducing template shoulder-yaw excursion from20.5° to10.3° preserved source leg
coordinates, but the matched NW generation in
[271](../experiments/271-half-yaw-nw-transfer/README.md) did not clearly improve
rear-left facing. Walking poses remained; arm/hair/coat details changed. This
candidate stays outside the default and is not being expanded to eight views.

The source's evaluated foot surfaces already dip below their nominal rest
minimum: [265](../experiments/265-source-foot-surface/README.md) measures this
without treating that reference plane as physical ground. Compare source and
generated low-foot intervals before attributing floor dipping solely to the
model or introducing a new contact correction.

For the existing Elias export, [267](../experiments/267-eight-direction-loop-seams/README.md)
found no exceptional wrap-edge pixel change in any direction, with no gross
position jump apparent in the static seam review. This does not approve
continuous playback, but gives no reason to add a loop correction to this case.

Require revised appearance conditioning to retain substantial walking on the
failed robot case as well as the hat/dress case before considering a default.
Evaluate motion and transparent exports on candidates that pass both requirements,
including additional independent artwork. Keep the installability,
ease-of-use and visual-quality requirements together: a successful CLI alone
does not finish the tool. The [year roadmap](animation-roadmap.md) retains the
broader scope and historical acceptance requirements.

## Action and timing experiments after the playable demo

- [354](../experiments/354-walk-timing-preview/preview.html) compares original,
  two-frame, three-frame and illustrative variable holds at unchanged cycle time.
  [355](../experiments/355-timed-godot-exports/README.md) verifies all24exported
  Godottracks retain1.333s; [356](../experiments/356-spritedx-texture-bridge/README.md)
  maps the actual atlas into SpriteDX texture fields without claiming full state integration.
- [360](../experiments/360-action-generation/preview.html) generated front idle,
  jog and sprint, each65frames in about60s. Running hands rise toward the face;
  [362](../experiments/362-jog-lowered-arms/README.md) lowering projected arms did
  not resolve it. [363](../experiments/363-side-jog/preview.html) side jogging
  retained facing in samples but lengthened legs/changed clothing. These remain
  experimental and are not production idle/run assets.
- [353](../experiments/353-seedance2-five-directions/attempt.json) records the
  requested regular Seedance2.0 five-view arrow-template attempt. No generation
  submitted or credits consumed: upload failure followed by browser-control
  rejection while Jin was using Chrome. No active hosted job to poll.
