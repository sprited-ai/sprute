# Animate with pinned first frames

`sprute-animate-character.anchor.api.json` is the animate workflow with three changes:

- `Sprute Hold First Frame` (600) puts five copies of the driver's first frame in front.
- `RepeatImageBatch` (601) feeds the gray-backed reference grid to `WanSCAILToVideo` as
  `previous_frames`, so the first five output frames are the reference itself.
- `ImageFromBatch` (602) drops those five frames. Output is 80 frames instead of 81.

Why: SCAIL2 picks front or back for the S and N cells from the initial noise. Seed 1 turned
the N cell to a front view for 5 of 6 characters. Pinned to the reference, every direction
starts from its own view.

Measured on gin, 2026-10-11, 21 runs with the same characters, motions and seeds:
10 flipped with the current workflow, 3 pinned. The pinned flips start right and turn
partway through. Silhouette IoU with the driver is unchanged; motion energy averages 0.92×
(one idle 0.40×). One pinned frame instead of five did not hold.

To try it: copy it over `workflows/sprute-animate-character.api.json`; node ids sprute's
CLI writes to are unchanged.
