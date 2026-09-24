# Local model storage

`scripts/sprute.py` reads models here by default. Large weights and fetched source
are ignored by git. `--models /path/to/models` selects another disk.

```bash
python scripts/sprute.py models setup
python scripts/sprute.py models download --stage generate
python scripts/sprute.py models download --stage turntable
python scripts/sprute.py models download --stage animate
python scripts/sprute.py models list
```

Downloads are explicit. Inference sets Hugging Face/Transformers offline mode.
The download command uses the Hugging Face cache and symlinks it here; it does
not make a second copy. To place that cache on a larger disk, set `HF_HOME`.
Gated models require your own HF access/license acceptance and `HF_TOKEN` or a
prior Hugging Face login. The tool never logs tokens.

You can link existing compatible models instead:

```bash
python scripts/sprute.py models link flux /data/FLUX.1-Fill-dev-diffusers
python scripts/sprute.py models link anisora /data/Index-anisora/V3.2
python scripts/sprute.py models link scail_model /data/wan2.1_14B_SCAIL_2_fp16.safetensors
python scripts/sprute.py models link dpo /data/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors
python scripts/sprute.py models link lightx2v /data/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors
```

| Link | Required format |
|---|---|
| `flux` | Complete Diffusers FLUX.1 Fill directory, including text encoders, tokenizer, VAE, transformer and scheduler |
| `anisora` | Official V3.2 directory: high/low model folders, native T5 checkpoint/tokenizer, Wan VAE |
| `scail_model` | Wan-native SCAIL2 safetensors; Comfy-Org FP16 or scalar `scale_weight` FP8 format |
| `scail_aux` | Official SCAIL2 directory with native T5, CLIP and VAE files |
| `xlm_tokenizer` | XLM-Roberta tokenizer directory |
| `dpo`, `lightx2v` | Wan-keyed LoRA safetensors |
| `birefnet` | Pinned BiRefNet Python/config directory; base weights aren't needed |
| `toonout` | ToonOut `.pth` or matching `.safetensors` weights |

**A renamed file is not a format conversion.** FP8 UMT5 files do not directly
substitute for native T5 weights. For SCAIL2, select a supported scaled-FP8
UMT5 checkpoint explicitly with `--text-encoder-fp8 PATH` instead of replacing
the native checkpoint link.
The default AniSora download is the much larger official unquantized pair
(roughly 114 GB for the two transformers alone). It is not downloaded implicitly.
FLUX's Diffusers weights also aren't a bare `flux1-fill-dev.safetensors` file.

The SCAIL2 loader restores scaled-FP8 checkpoint weights into BF16 before
applying DPO and LightX2V. `--precision fp8` then quantizes the fused Linear
layers for execution. Loading an FP8 file therefore does not bypass runtime
quantization or keep the model in FP8 throughout startup. The default download
is still FP16. Tiny upstream-model tests verify scale restoration and LoRA
arithmetic; full-size quality comparisons are separate from these checks.

### Existing linked weights on gin

The native loader also supports these explicitly assembled layouts. All large
files are symlinks; configuration/tokenizer files come from the pinned model repos.
Neither layout imports ComfyUI or calls its server.

- `flux/`: Diffusers configs, scheduler and tokenizers, with
  `transformer/original.safetensors` pointing to FLUX Fill,
  `vae/original.safetensors` pointing to `ae.safetensors`, and
  `text_encoder/model.safetensors` / `text_encoder_2/model.safetensors`
  pointing to CLIP-L / T5XXL FP16. Original BFL keys are converted in memory.
- `anisora/`: the official layout above, but HIGH/LOW weights may point to the
  KJ scaled-FP8 files when `scaled-fp8.json` exists at the root. The adapter checks
  all parameter names and shapes and applies each `scale_weight` during BF16
  loading by default. This does not recover original precision.
  `turntable --precision fp8` (or `run --turntable-precision fp8`) instead
  uses FP8 Linear kernels and retains their FP8 weights during inference.
  See [precision options and measurements](../scripts/README.md#individual-stages).

The prepared gin links live at `/mnt/stash/sprute-native-cli/models/flux` and
`/mnt/stash/sprute-native-cli/models/anisora`.

`_sources/` contains pinned official AniSora and SCAIL2 code, not ComfyUI.
Their licenses remain their own. Model licenses/access terms also remain
independent of Sprute's MIT license; do not redistribute all weights as MIT.
