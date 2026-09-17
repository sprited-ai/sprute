# Sprute v2 proposals and experiment record

Snapshot: 2026-09-17. Repository: `/Users/jin/dev/sprute`; branch based on its current `main` checkout. The separate `sprute-2` repository is outside this work.

Jin owns the v2 architecture and scaffolding. This branch collects evidence and small, reviewable proposals; it does not implement the new CLI or imply the proposed commands work today.

- [Learnings](learnings.md): observations, failures, and product implications.
- [Pipeline contract](pipeline-contract.md): proposed artifact boundaries, sizing, timing, provenance.
- [Local artifact index](local-artifacts.json): paths and hashes for this session's assets. Files outside Git remain local.
- `repro/`: archived rendering/postprocessing scripts and sanitized inference requests. These are snapshots with absolute local paths, not portable production commands.

## Merge order

1. Repository hygiene (`.gitignore`); retain examples and documentation media.
2. Experiment record and pipeline contract, reviewed by Jin.
3. Later, selectively adapt small pieces into Jin's architecture. Do not bulk-merge the old experimental pipeline.

The original checkout's untracked `experiments/` directory is ignored, not deleted. Already tracked experiments stay tracked. Intentional source promotion can use `git add -f` after review. No global media ignore rules: PNG/WebP/MP4 examples remain eligible for version control.

## Implemented starting scripts

See [scripts/animation](../../scripts/animation/README.md) for the two standalone pipelines and preserved idle/walk/run driver videos. The v2 CLI remains Jin’s work.
