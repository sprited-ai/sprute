# Consolidation baseline — 2026-09-15

This checkpoint collects the standing-character, animation, local-runtime,
preview, and export work before the next repository reorganization.
It is a tested development baseline, not a new npm release.

## Verification

- `pnpm exec tsc --noEmit`: passed.
- `pnpm test`: 40 files, 139 tests passed.
- `python3 runtime/test-install-models.py`: 6 tests passed.
- `pnpm build`: JavaScript bundles and TypeScript declarations passed.
- `npm pack --ignore-scripts`: package created after the successful build.
- Installed that tarball in a fresh temporary project with normal optional
  dependencies enabled: CLI login and all four public package entry points passed.

The publish workflow now requires type checking, TypeScript tests, and the
model-installer tests before building and publishing.

## Boundaries for the next reorganization

- Keep paid-provider submission and recovery together. The Replicate image path
  still assumes a completed synchronous response and does not retain a job ID.
- Route command forms through a common build lifecycle. Prompt/config builds and
  character-spec builds currently have different caching and recovery behavior.
- Consolidate configuration validation and credential resolution.
- Preserve existing integrity checks, exclusive submission claims, and approved
  fixed-direction pixels when moving modules.
- Distinguish saved artifact reuse from reproducible generation; the Replicate
  request currently does not submit the seed recorded in entity metadata.
- Expose review failures and fallback processing in structured build results.

No paid model generation, GPU inference, npm publication, or remote push was
performed for this checkpoint. The checks above do not certify visual quality
or reproduce the experimental CUDA environments.
