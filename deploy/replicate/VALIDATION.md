# Hosted validation — 2026-10-02

## Conclusion

Individual public stages work. Full cold-start prompt-to-three-motion execution is not reliable within the 20-minute limit; keep the PR in draft.

Runtime: shared Cog CUDA 12.8 / Python 3.12 / PyTorch 2.8.0 base, Cog 0.16.8; H100. Latest version: `21a45f2dc70df98fce4f3ae9f208149a4f020e8843fdc4ea5bca61faeae6ce3f`.

| Stage | Inference seconds | Device-wide peak GiB | Result |
|---|---:|---:|---|
| Generate | 40.754 | 24.00 | Passed, PNG inspected |
| Turntable | 38.438 | 16.12 | Passed, strip and two WebPs downloaded |
| Idle | 177.510 | 57.71 | Passed |
| Walk | 181.459 | 57.71 | Passed |
| Run | 182.709 | 57.71 | Passed |

Timing includes per-stage loading, driver rendering and postprocessing. Memory is sampled whole-device usage, not minimum VRAM. Animation uses scale 1.0 and seed 42. The three-motion request took 1094.0 s including cold start/downloads; inference alone took 541.767 s.

## Evidence

- Generation: `3wkapqfzwxrnc0d0zdjtjmdta4`; same-worker follow-up `mc8c9a9ytdrn80d0zdr9xhj8jr` completed in 36.7 s with pixel-identical output.
- Turntable: `9h1c6csehnrp40d0ze4sqc1nem`. Outputs: 1536x256 RGBA strip; 192x256, 81-frame turntable; eight-frame direction preview.
- Animation: `84av9b4eghrnc0d0zmgtk7wjsg`. All 243 RGBA frames decode; each motion is 1536x256, 81 frames, 3321 ms. All frames contain foreground and transparent pixels.
- Sampled direction and temporal sheets preserve character identity and show distinct walking/running leg motion. No guarantee of seamless loops or reliability across characters/seeds.
- 30 automated tests passed in the runtime image, covering stage skipping, motion selection, seed/scale propagation, integrity checks, cache reuse, deadlines, process cleanup, single submission, and artifact preservation.

## Failures and fixes

1. Replicate's injected Hugging Face proxy returned truncated bodies. Direct public Hugging Face HTTP downloads allowed successful stage runs.
2. Full cold downloads total 93.23 GB. Three concurrent stage-ordered downloads timed out after 600 s. Largest-first, five-concurrent downloads completed in 487.2 s once, but another full attempt still timed out on FLUX.
3. Full default request `q0r3fhznjnrn80d0zkzt446d7r` completed downloads, generation, turntable and idle, but exceeded the overall 20-minute deadline. Cancellation was confirmed. This is not full E2E success.
4. Inference now gets up to 900 s within a 1200 s overall prediction budget; downloads remain capped at 600 s. API test deadlines also include startup and are capped at 20 minutes.
5. A prior successful three-motion request's media expired after an SSH interruption. The monitor now runs independently of SSH and downloads artifacts immediately. The repeat above has been retained and visually checked.
6. The scale-0.5/random-seed full request failed before inference because of model downloads. Those hosted controls remain unverified; default-scale/fixed-seed inference is verified.

Cache reuse is worker-local and routing to the same worker is not guaranteed. No further automatic paid test sequence is scheduled. The historical orphan prediction is separate from these tests. Kimodo remains an internal experiment, not a public model input, and was not hosted-tested here.

## Artifacts

Local evidence is under `output/hosted-e2e/` (gitignored): `animations.gif`, `animation-midpoints.png`, `front-contact-sheet.png`, `side-motion-check.png`, `media-checks.json`, and the downloaded files/logs/metrics in `animate/` and `turntable/`.
