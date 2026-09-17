# Proposed artifact contract (for Jin's review)

Keep separate stages: reference → standing views → raw motion → cropped direction frames → matted frames → registered/exported animation.

Suggested manifest fields:

- Schema version, character identifier, state and direction order.
- Source reference and driver hashes; template version and exact composition rectangles.
- Provider/model/version if exposed, exact prompt/negative prompt, settings, prediction ID and timestamps.
- Requested resolution versus actual decoded width/height/frame count/timebase.
- Raw immutable result location; separate postprocessing outputs.
- Matting model/version/hash, process resolution, edge/refinement settings.
- Fixed cell width/height, anchor and scale transform; distinguish layout normalization from measured character registration.
- Source frame range, loop selection method, seam score and human-review status.
- Codec, quality, alpha, durations, and measured byte size.
- Estimated cost separately from actual billed amount; include failed/uncertain submissions.

Resume by recorded prediction ID. A submission timeout is not permission to submit again. Avoid unrequested image-model repair calls. Capture known limitations (mirroring, text changes, facing flips) rather than silently labelling a result validated.

## Export invariant

For a matching still/run strip, both have eight cells with identical dimensions/order/anchors. Register character scale separately using a stable reference over the whole cycle, then apply a fixed transform. Changing the pose naturally changes its bounding box; equality of instantaneous bounding boxes is not the objective.

## Hygiene

Keep heavy experiments and model files outside source control. Check in small reviewed scripts, manifests without secrets/data URIs, and selected demo assets. Ignore rules do not untrack existing files or back up ignored local data.
