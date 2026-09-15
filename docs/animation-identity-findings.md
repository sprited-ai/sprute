# Identity findings from the asymmetric robot

[261](../experiments/261-upper-front-reference/README.md) compares single E,
duplicate E upper-mask and extra S upper-mask references without a temporal
anchor. All195 frames/timing were verified; all contacts and native0/16/32/48/63/64
were inspected. Extra S retains changing limbs/right-facing orientation and
locally reduces a disrupted arm contour, but source face/hat/hair/clothing still
redraw. No clear overall identity restoration is established; do not promote or
expand by default. This avoids the near-static failure of257 but does not solve
source fidelity, gait/contact/loop or alpha quality.

[260](../experiments/260-robot-anchor-pose-strength/README.md) doubles pose
strength1→2 while retaining257's source anchor. All130 paired frames/timing
passed. Full contacts and selected native16/32/48/wrap still show near-standing
behavior with increased background/surface variation. Yellow centroid x range
in32–63 rises7.26→12.98px, far below the unanchored109.40px; this is a color-region
measurement, not joint tracking. Reject the candidate and stop the strength
sweep as planned. Neither anchored setting is a general walking default.

[257](../experiments/257-robot-source-anchor/README.md) is a decisive motion
counterexample for the one-source-frame anchor at E/seed7/CFG3. All130 paired
frames/timing were verified. The full candidate contact and native16/32/48/wrap
show closer standing resemblance, but walking leg separation is largely lost:
the sequence stays near-standing with small changes. Selected yellow-boot
regions also acquire blue patches. Reject promotion as a general walk default;
appearance-only improvement on the hat/dress character is insufficient. The
baseline itself retains hand/neck artifacts and is not a quality-approved fix.

[252](../experiments/252-side-five-frame-anchor/README.md) completed the matched
E/seed7 one-versus-five anchor comparison. All130 paired frames and timing
passed verification. Contacts and selected native16/32/48/64/wrap show both
variants retain a recognizable side face/hat/dress, with detail still redrawn.
Five frames change arm/hand poses but do not establish a clear overall identity
improvement here. The front speckle reduction in251 therefore remains a bounded
finding. Both comparisons have labeled playback files; continuous motion,
contact, loop and alpha quality remain unapproved. No default changed.

[251](../experiments/251-five-frame-source-anchor/README.md) compares one versus
five repeated source-frame anchors on S/seed7. All130 paired frames/timing were
verified; contacts and selected native16/32/48/wrap were inspected. The obvious
arm/shin mottling is substantially reduced, while eyes/face and garment details
still redraw. Changing foot poses are visible but motion/contact/loop/alpha are
unapproved. This is a front-view candidate result, not evidence to change the
integrated default; side-view behavior remains to be tested.

[250](../experiments/250-side-anchor-second-seed/README.md) completed paired
E/seed123 unanchored and anchored runs. All130 frames and paired timing were
verified; contacts, selected native frames and wrap were inspected. Visible
side-facing facial detail improves versus the matched baseline, but floral
texture and shoes still drift. This partially replicates249's benefit, not
full artwork preservation. Keep the anchor as a research candidate; no default
change follows. The front speckles and gait/contact/loop/alpha gates stay open.

[249](../experiments/249-hat-dress-side-anchor/README.md) completed the same
single-frame anchor on E/seed7. The 130 paired frames/timing were verified and
candidate contacts plus selected native late frames inspected. Face/hair/hat
retention improves relative to the unanchored E baseline, with changing limb
poses. The selected native samples do not show the S case's equally prominent
speckling, but this is not comprehensive artifact or gait clearance. Combined
with 248, this supports a bounded paired second-seed test, not default promotion.
The front artifacts and motion/contact/loop/alpha gates remain open.

[248](../experiments/248-hat-dress-first-frame/README.md) connects the source
image to the existing one-frame prior input, with other 245 S settings fixed.
The completed candidate retains more source-like face/hat/pixel treatment in
late inspected frames than baseline, but develops mottled arm/shin patches at
16/48 and has less separated selected frontal foot poses. The 130 paired frames
and timing passed verification. This is an appearance candidate only, with no
motion/contact/loop/alpha or cross-view acceptance. Keep defaults unchanged;
a matched side view is needed before judging stride behavior or generality.

[247](../experiments/247-hat-dress-cfg-one/README.md) tests CFG3→1 against the
245 S/seed7 baseline, changing only CFG and output prefix. Both videos' 130
frames and paired timing were verified; candidate contacts, selected identity
pairs and native wrap comparison were inspected. The source face/hat/style
loss remains, despite changed garment and shoe rendering. CFG1 is not promoted.
Visible changing foot poses do not close gait/contact/loop/alpha requirements.
This single case rejects CFG reduction as a sufficient fix, not every possible
CFG value or a particular conditioning mechanism.

[246](../experiments/246-hat-dress-vae-control/README.md) completed the matched
S/E reference VAE control for 245. Same-size preprocessing was pixel-exact;
the real pinned VAE introduces softness and texture changes but does not
reproduce the large smooth-cartoon redraw seen in generated frame 0. Both
three-column comparisons were inspected with verified source/output hashes.
Plain reference reconstruction damage alone is therefore insufficient to
explain this failure. Investigate conditioned generation next; this does not
identify a specific layer or exonerate decoding of generated latents.

Current additional-character screen:
[245](../experiments/245-scail-hat-dress/README.md) completed blue-dress S/E
under the unchanged 201 SCAIL settings. All 130 frames were verified and
inspected on contacts, with selected native reference pairs and 128-pixel
comparisons. Hat/ribbon/dress/shoe categories remain, but the source face,
hair, clothing detail and rendering treatment change before matting. Neither
view is accepted as preserving the source artwork; the remaining directions
were not submitted. This character was used in older experiments, so it is
not an unseen-character validation. Motion/contact/loop and alpha gates remain
open. A matched reconstruction control is the next diagnostic, not another
uncontrolled caption or eight-direction batch.

Current diagnostic correction (141): an unchanged source shin under fixed N
lighting becomes visibly brighter and develops horizontal bands under rigid hip
rotation. Therefore a pale shin alone is not sufficient evidence of material
drift. Historical brightness observations below remain observations; their
material-error interpretation is unproven without pose/surface/lighting matching.
The N counterexample does not establish that any particular S or N generated
frame is correct. No quality status is promoted to accepted by this correction.

Keep separate evidence separate: invented cyan/oval head-side markings and the
localized boot spikes at132 frame38 have independent visual evidence.133 shows
rounded boots alone are also not enough to prove deformation.134/136 reduce
some such artifacts at CFG3 on S, but137/140 retain rear shin brightness changes
whose physical explanation is unresolved. All those jobs are complete. See the
roadmap and per-experiment assessments for current scope; earlier paragraphs
describe the historical sequence, not live queue state.

120 completes the driver-chroma pair: RGB and grayscale lossless65-frame
inputs, all130 output contacts and native0/16/32/48/64 reviewed. Both retain
pale right shin and cyan head-side artifacts. Chroma removal is not a fix for
S seed7. No production default change; input-format compatibility, shading/shape
influence and reference conditioning remain unresolved. 121 finds a32-frame
repeat minimum in all8 baselines, but no gait-phase/loop acceptance. 122 review
UI passes isolated Chrome interaction checks; no human playback QA claimed.

117 finishes the seed7 eight-direction baseline: all four diagonal videos have
65-frame contact review and selected native inspection. Diagonal facing and key
colors are retained in reviewed samples; motion/contact/phase/loop/alpha remain
unaccepted. S/N/E/W failures mean the full set is not usable yet. 119 adds only
an explicit charcoal-shin sentence to116 S/N: all130 contacts and native failure
phases reviewed; pale shins remain in both, plus S head-side cyan. Caption-only
fix rejected; no production default change. 118 holds the verified comparison.

116 S/seed7 completes the first front-view baseline: all65 contacts and
native0/16/32/48/64 reviewed. Cuff/boot colors retain sides, but unwanted cyan
head-side markings and a pale right shin appear at16/48. Appearance consistency
rejected. N also completes: all65 contacts/native0/12/16/28/32/48/64 reviewed. Rear
facing and cuff/boots retained, but shins turn pale at12/28. S has independent
head-side identity evidence; N brightness-only rejection is qualified by141.
All four117 diagonals subsequently completed and were reviewed as candidates.
No played-loop/contact/alpha acceptance.

115 reviews TransAnimate's paper and author pages: image/sketch control is
described, but trajectory directions do not establish eight character views.
Official source/weights were not located in the checked sources; licenses and
reference-plus-articulated-motion compatibility remain unverified. Research
lead only; resume the existing route's missing directional evaluation.

114 audits direct-RGBA alternatives at pinned commits: Wan-Alpha v2 declared
reference/video flags are unused in actual generation; I2V weights still on its
roadmap. TransPixeler main CLI is T2V with research-only source license. Neither
is a verified character-reference + motion-driver replacement. No model run or
production change; controllable RGBA compatibility remains open.

113 tests actual PyMatting1.1.15 closed-form alpha with automatic versus manually
unknown antenna/scarf regions. Both fail: automatic keeps opaque artifacts;
guided unknown removes them but loses thin/scarf foreground. Native comparison
reviewed. Not integrated; stronger foreground constraints or direct/preserved
RGBA warrant investigation, not another automatic-default claim.

112 is a reproducible negative alpha control: a35%-opaque scarf becomes almost
opaque (mean alpha88.95→251.99); thin-line retention is60.89%, while1830 known
blank antenna-region pixels become alpha>=128. RGB inverse does not repair it.
Two identical runs/native comparison reviewed. Preserve as a rejection case for
future alpha methods; no arbitrary-transparency claim or default correction.

111 tests the background inverse on all32 E seed7 generated matte frames.
Exterior median230 is stable across frames; alpha and opaque RGB unchanged.
Dark contacts/native8/16/31 show partial fringe reduction, with residual outlines
and clipping. No temporal/translucent-case validation or default adoption.

110 reproduces fringes on known-alpha E render: true alpha with flattened RGB
still has partial-edge dark-composite MAE19.46. Known232 background inverse drops
that to0.18; with ToonOut alpha it only drops26.31 to18.94 and fringe remains.
Two repeat hashes match. Both RGB contamination and alpha error matter; no
production correction or generated-video alpha truth is established.

109 produces32 local transparent E seed7 frames from108. RGB, source indices and
timing verified unchanged; output hashes recorded. All32 checker contacts and
native0/16/31 inspected without gross body deletion. Temporal alpha, fine halos
on other backgrounds, played loop and contact remain unaccepted.

108 extracts E source32–63 candidates from105/106 with source/frame hashes and
timing retained. Boundary contacts inspected; no gross pose reset apparent, but
playback, foot contact and transparent edges remain unreviewed. Not accepted loops.

107 W pair is complete:130 contacts and native0/16/48/54/64 inspected. Both
full and upper masks retain visible identity and alternating legs. Upper-mask54
adds a detached gray oval below lifted blue boot, absent in full54. Initial
brightness/blur remains. E motion recovery does not justify a universal mask
default. Contact/played loop and other six views remain unresolved.

109 dark-background follow-up shows thin light fringes around parts of hands/
torso at native candidate16. All32 dark contacts inspected. Checker-only alpha
review understated the fringe; fine edge quality remains unaccepted.

106 E/seed7 replication is complete: all65 contacts/native0/16/48/64 inspected.
Upper-only extra mask retains red cuff, boot colors and alternating legs, without
the pronounced seed123 initial brightness shift. Full-mask101 already moved;
this supports second-seed stability, not another recovery. Motion changes remain
and do not establish driver fidelity. Next run prepared107 W mask pair.

105 is complete: full extra RGB with upper-only mask restores alternating legs
in E seed123. All65 contacts/native0/16/48/64 inspected. This changes only the
mask relative to102, so removing lower-body RGB is not necessary in this case.
Stride increases beyond104 and093; greater range is not gait accuracy. Cuff/boot
colors retain, initial brightness/edge blur remain. Replicate E seed7 against101;
no default/contact/loop or cross-view acceptance.

102 paired replication is now complete: both duplicate and complementary E seed123
fail walking, with legs largely frozen in the standing reference pose. All130
contacts plus native0/16/48/64 inspected. Complementary upper-body appearance is
cleaner, but that does not rescue motion. No default promotion;103 W expansion
deferred. Investigate extra-reference lower-body pose bias before further batches.

104 recovers alternating leg movement with upper-body-only extra RGB and mask,
compared with frozen legs in 102 E/seed123. All65 contacts and native0/16/48/64
inspected; cuff/boot colors retained, initial brightness/edge blur remain. This
supports lower-body reference interference but does not isolate image from mask.
Next retain full extra RGB with upper-only mask. No default or loop/contact acceptance.

Earlier diagnostic findings below are historical; 102's motion rejection governs
current adoption decisions.

Complementary-pose101 is promising in one E/seed7 case: red cuff and boot colors
retained, no obvious yellow neck patch at native16/48, and simpler torso edge
than both side-only093 and duplicate100. All65 contacts/native0/16/48/64 inspected.
Arm swing and stride also change; no motion/contact/loop acceptance. Replicate
with a matched seed123 control before extending the finding to other views.

Duplicate-reference100 narrows the multireference diagnosis: E/seed7 with the
same side image twice retains the red far cuff in native16/48 and avoids the
pronounced initial warm/bright change seen with a frontal extra. All65 contacts
and native0/16/48/64 reviewed. Yellow neck/torso artifacts remain. Extra-reference
content matters; this does not isolate viewpoint from posture/duplicate weighting.
Next compare complementary poses from the same viewpoint. No quality acceptance.

VAE diagnostic099: independent and temporal encode/decode of the actual E/W/S
references retains visible red cuffs and boot colors across12 reviewed outputs.
Fixed-coordinate red retention is94.84–99.32%; this is a narrow visibility check,
not identity acceptance. Simple VAE reconstruction damage alone does not explain
the red-to-gray generation failure. Investigate conditioning use under motion/
occlusion next; do not infer a specific attention-layer cause from this test.

Temporal-reference098 also fails the tested E/seed7 case: all65 contacts and
native0/16/48/64 inspected. Far red cuff becomes gray, yellow neck detail remains,
and early warm/bright appearance persists, as in093 independent multi-reference.
Only encoding/routing changes; no default promotion. One case does not disprove
all temporal-reference schemes. Next isolate reference VAE reconstruction damage
before expanding diffusion comparisons.

DPO follow-up096: official checkpoint provenance and 400 structural LoRA pairs
verified; actual Comfy loader attached400 patches. E/W seed7 completed, with130
contact frames and selected native comparisons inspected. E retains its yellow
neck artifact and changes stride. W loses the blue boot near the end, producing
two yellow boots in native frame64. No DPO default promotion; seed123 candidates
deferred after this regression. No loop/contact/all-eight-direction acceptance.
Exact paired workflows and assessment scope are in experiment096.

SCAIL comparison093 is complete: eight outputs, E/W × seeds7/123 × side-only or
side+front. All520 contact frames and selected native comparisons were inspected;
all workflow/video/frame hashes verified. None has full animation-quality acceptance.

| Pair | Effect of adding a front reference | Decision |
| --- | --- | --- |
| E seed7 | Far red cuff becomes gray; yellow neck artifact remains; early appearance changes | Reject extra-reference variant |
| E seed123 | Blue boot becomes yellow; early appearance changes | Reject extra-reference variant |
| W seed7 | Colors retained; arm pose changes; olive rear-neck artifact remains | Neither variant accepted |
| W seed123 | Colors retained; occluded geometry unresolved; early appearance changes | Reject extra-reference variant |

No multi-reference default promotion. Retain the side-only configuration as an
experimental baseline, not a finished animation solution. Address occluded-part
geometry and persistent identity before expanding generation broadly. Foot contact,
cross-direction phase, loop playback, alpha edges and arbitrary characters remain
separate requirements.

These use SCAIL fp8,40 UniPC/simple steps, CFG5, shift3 and no LoRA. They are
within-SCAIL paired tests, not one-variable comparisons with earlier WAN results.
Input/model/decoder/VAE checks are in088–092; exact workflows, videos and review
scope are in093. 095 confirms source cyan chest visibility can change with arm
swing; cyan visibility alone is not an invented-part failure.

The original076 robot has one red anatomical-left cuff, a blue left boot, a yellow right boot, dark featureless hands, and no side-head decoration. All eight standing references are independent renders. This is a controlled procedural character, not evidence for arbitrary user artwork.

| Experiment | Change from077 | Observed result | Decision |
| --- | --- | --- | --- |
| 077 | Side reference, side CLIP, side motion | E invents a pale finger-like hand; W duplicates red cuff and blurs yellow boot | Reject E/W; other views unapproved |
| 078 | E explicit dark fingerless hand caption | Pale finger-like hand remains | Insufficient |
| 079 | E/W target CLIP uses frontal image | E hand darkens but shape/cuff incomplete; W defects remain | No default change |
| 080 | E/W VAE reference uses frontal image | Cuff improves, but side-head details invented and boots change color | Reject both |

Each variant used seed42, Euler10, CFG1,65frames512px and fixed side motion. 078 has65 reviewed frames;079/080 each130. All-frame review means contact sheets supplemented by specific native-size comparisons, not exhaustive edge inspection or proof of smooth playback. Exact prompts, graph differences, journals, collected hashes and review scope live in each experiment folder.

The installed WAN Animate 2 node uses only reference_image[:1] for its VAE reference. A plain image batch is not a multiview spatial reference mechanism in that node. This restriction does not describe the separate SCAIL node tested in088–093. CLIP and VAE carry distinct conditioning and should not be described interchangeably.

Next implementation should preserve side-specific spatial appearance while adding explicit information for hidden parts, or use a representation with persistent part identities. Before committing to another model change, define how extra views map to parts and how the model receives that information. This is a design requirement inferred from these failures, not a validated solution. A collage, untrained extra latent frame or global recoloring must not be advertised as multiview consistency without an actual test.

Keep E native16/48 (hand), W0/33 (cuff), W15/47 (crossing), and every frame's boot color as regression evidence. Also reject newly invented side-head details, frontal turns, mirrored anatomy and leg topology changes. Re-run other directions and independent user characters before any release claim. Contact, shared phase, loops, transparency edges, reproducible installation and a beginner workflow remain separate open requirements.


## 081: expose both arms at the same side angle

Rotating original arm groups±35degrees about shoulders exposes the otherwise hidden cuff and hand while preserving side cameras, geometry and colors. All130frames reviewed on contact sheets, with baseline comparisons0/16/33/48 for both directions and W15 native inspection. E red cuff and dark hand are recovered, though hand becomes fist-like. W cuff duplication is absent in reviewed frames and W15 yellow boot no longer has baseline pale blur. No080-style side-head additions observed.

This supports further testing of same-view reference posture. It does not isolate visibility from posture/normalization, establish seed robustness, or recover hidden parts from arbitrary artwork. Next test paired additional seeds using077/081 inputs before promoting this as reference guidance, and address remaining hand geometry. All quality gates remain open.

## 082: additional paired seeds

Seed7 E recovers the red far cuff with the posed reference, but finger-like hand
detail remains. Seed7 W removes duplicated red and the cyan ring-like hand detail
at native frames0/33, yet the far cuff is incorrectly blue at0. The posed blue
boot becomes teal at16 and reddish at54. The original W reference also produces
boot recoloring, so neither variant passes persistent part-color identity.
These findings prevent promoting exposed-arm references as a general fix.
Seed123 E/W results are also reviewed: all260 contact frames plus E0/16/48 and
W0/16/33/48 native comparisons. E already has a red far cuff in baseline; posed
improves its visibility and removes early two-blue-boots frames. W removes red
cuff duplication at0/33, with no obvious boot hue replacement on either contact
sequence. Finger-like hand detail persists in both directions. None is approved
for contact, anatomical part ownership through crossings, phase, seams or alpha.

The prespecified seed7/123 comparison is complete, with all eight workflow/video
hashes verified against the frozen plan and collection metadata. Together with
the earlier seed42 it supports a limited reference-posture effect, not a general
identity fix. Retain the W-seed7 posed color failure in future evaluations. No
production reference default changes follow from this experiment.

## 085: late motion-condition window

Changing only pose_end_percent1→0.7 (plus output prefix) on082 posed references
does not fix the reviewed seed7 defects. E retains finger-like hand detail at
native16/48; W retains teal/reddish boot recoloring at16/54. Both full65-frame
sequences were inspected on contact sheets, without contact/phase/seam approval.
Seed123 pairs are now collected and reviewed on130 contact frames and native
E16/48, W0/33 pairs; finger-like details remain. All four candidates are unapproved. This result tests one schedule window, not the hypothesis of
appearance leakage in general. No default change follows from it.

## 086: gray motion-source appearance

The pinned rig was rendered gray with the same action samples and cameras;
source-bones.json matches the blue source byte for byte. Motion video, matching
first-frame CLIP image and the motion caption's color word changed together.
All four E/W seed7/123 candidates are collected and260 contact frames plus
selected native pairs reviewed. E16/48 in both seeds and W-seed123 0/33 retain
finger-like hand details. W-seed7 expected blue boot becomes green at16 and
orange at54, replacing the blue-source run's incorrect teal/reddish colors.

This bundled input change affects the erroneous hues without recovering identity.
It neither proves a specific conditioning channel caused the errors nor supports
gray as a general fix. No default promotion. Further work must address persistent
part identity through occlusion and exact source geometry; simply adjusting
motion-source color has not met either requirement in this comparison.
