# Local standing direction control

The experiment 392 orchestrator completed eight files, but native-resolution
review rejected the set: the requested SE faces left and duplicates SW. Its
`status: complete` is an execution status, not visual approval. Do not use this
set as eight correct animation references.

| Trial | Input/control | Observed result |
| --- | --- | --- |
| 394 | Original front, explicit bottom-right face/body/shoes prompt | Still front-left; rejected |
| 395 | Original front plus a different character's correct SE reference | Wrong direction and substantial identity/style drift; rejected |
| 396 | Same character's generated E, request a 45-degree turn toward camera | Retains strict profile; rejected |
| 397 control | Original front, camera-left45 wording, no angle LoRA | Front-left |
| 397 adapter | Same settings as control, angle LoRA1.0 only | Front-right candidate, but softer and taller/slimmer; not adopted |

Trial 397 used Qwen-Image-Edit2509 FP8, seed42,1024 square,20 Euler steps,CFG4,
AuraFlow shift3. It did not use Lightning. The installed angle adapter was hashed
against the recorded upstream SHA256 before loading. Its effect is isolated by
the paired same-prompt control; this does not prove general camera-angle accuracy.
Trial 398 changes only the adapter-condition seed to7; its outcome must be read
from the saved review rather than inferred from model process completion.
The completed seed7 result repeats the slight front-right bias and preserves
framing, but is still front-dominant with the same proportion/style drift. Both
seeds remain candidates, not accepted SE sprites.

Do not replace incorrect directions by silently swapping labels or mirroring an
asymmetric character. Review face, torso and feet together. A right-facing
profile is E, not a successful SE. Neither detector confidence nor eight output
files supplies this visual evidence. Pose fitting and animation orchestration
remain disconnected while the standing references are rejected.

The earlier 387 angle trial combined an angle adapter with four-step Lightning;
its cropping failure cannot be attributed to the angle adapter alone.

Trial399 changed only camera-left45 to camera-right45 versus397 adapter.
Manual review found an opposite front-left face/body direction. This supports
left/right control on this source at seed42; it does not validate eight angles,
exact45-degree rotation, a second character, or production-quality identity.

Trial400 completed before the turntable pivot. Its90-degree request produced a
right-facing profile;180 also produced a right-facing profile rather than a back
view. This configuration does not cover the full requested azimuth range.

The alternative One-to-All turntable trial401 produced temporal turning but
failed rear-torso consistency and neutral standing pose; Jin rejected its visual
quality. Trial402 rendered a planted-leg conditioning clip only, with no video
inference submitted. Repeated turntable generation has stopped.

Current decision: neither approach is accepted for automatic eight-direction
standing generation. Keep the existing working animation/export components,
but do not promote these direction experiments or feed rejected views to them.
