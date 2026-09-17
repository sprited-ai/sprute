# Sprute 1.0.0

This release freezes the current character-generation and experimental animation implementation before the planned 2.0 redesign.

## Included

- Generate eight-direction standing sprites from a reference image or text through Replicate.
- Local credential storage, background removal, standing previews, and reusable character builds.
- Experimental ComfyUI-backed walking pipeline: preparation, submission/resume, collection, matting, atlas packing, browser review, and Godot export.
- Existing programmatic exports for core, build, web, and ToonOut remain available.

## Requirements and limitations

- Hosted image generation requires a Replicate API token and paid inference.
- Walking requires a separately configured ComfyUI GPU server, model weights and motion guides. Blender and FFmpeg are needed for the documented preparation workflow.
- Some standing directions are mirrored; asymmetric details may change sides. Generated motion, facing, loop seams and matte edges require visual review.
- The Seedance experiments and proposed 2.0 commands are not part of the 1.0 product interface.
- Local uncommitted research artifacts are excluded from this release.

## Validation

Passed TypeScript checking, all 139 tests across 40 Vitest files, all 6 Python model-installer tests, production build, package-content inspection, and isolated package-install/import smoke checks.
