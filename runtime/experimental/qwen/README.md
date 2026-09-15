# Local Qwen image runner

`python generate.py --job job.json` calls installed Comfy Python modules directly,
without starting a server. Requires configured Linux CUDA/Python and local models.
No cloud fallback; offline HF/Transformers flags are set. This is an experimental
image execution component, not yet a complete character-state compiler.

Job fields: reference (image path), optional guide (second image), comfyRoot,
diffusionModels (directory), output (new directory), prompt; optional seed42,
width1024,height1024. Paths resolve relative to the job file. Dimensions256..1024,
multiples of16. Existing output is refused. Models are QwenEdit2509FP8,
Qwen2.5VL7BFP8 text encoder and QwenVAE, with no LoRA;20steps,CFG4,Euler/simple.

Autograd is disabled. Models are offloaded between phases.28GiB PyTorch allocator
cap is an experimental guard, NOT a full-device memory measurement: Comfy's
custom allocators and external CUDA allocations may be outside its accounting.
A real32GiB GPU acceptance run remains necessary. Host RAM is also unqualified.

Outputs: job.json,state.json,latent.pt (detached CPU samples),result.png. Intermediate
latent enables future decode-only recovery, but this script does not yet implement
resume. Do not rerun failed jobs without inspection. Successful execution does not
mean correct character identity, facing or a game-ready sprite.
