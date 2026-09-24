from pathlib import Path
from huggingface_hub import hf_hub_download

MODELS = {
    # Generate: FLUX
    "flux-fill": {
        "repo_id": "black-forest-labs/FLUX.1-Fill-dev",
        "filename": "flux1-fill-dev.safetensors",
        "revision": "358293da0354175698b67ec8299acf928313a78a",
        "destination": "diffusion_models/flux1-fill-dev.safetensors",
    },
    "clip-l": {
        "repo_id": "comfyanonymous/flux_text_encoders",
        "filename": "clip_l.safetensors",
        "revision": "6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5",
        "destination": "text_encoders/clip_l.safetensors",
    },
    "t5-xxl": {
        "repo_id": "comfyanonymous/flux_text_encoders",
        "filename": "t5xxl_fp16.safetensors",
        "revision": "6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5",
        "destination": "text_encoders/t5xxl_fp16.safetensors",
    },
    "flux-vae": {
        "repo_id": "black-forest-labs/FLUX.1-Fill-dev",
        "filename": "ae.safetensors",
        "revision": "358293da0354175698b67ec8299acf928313a78a",
        "destination": "vae/ae.safetensors",
    },

    # Turntable: AniSora
    "anisora-high": {
        "repo_id": "Kijai/WanVideo_comfy_fp8_scaled",
        "filename": "I2V/AniSora/Wan2_2-I2V_AniSoraV3_2_HIGH_14B_fp8_e4m3fn_scaled_KJ.safetensors",
        "revision": "033a4e487f60220b3d6e469599a6aebc46e13cee",
        "destination": "diffusion_models/Wan2_2-I2V_AniSoraV3_2_HIGH_14B_fp8_e4m3fn_scaled_KJ.safetensors",
    },
    "anisora-low": {
        "repo_id": "Kijai/WanVideo_comfy_fp8_scaled",
        "filename": "I2V/AniSora/Wan2_2-I2V_AniSoraV3_2_LOW_14B_fp8_e4m3fn_scaled_KJ.safetensors",
        "revision": "033a4e487f60220b3d6e469599a6aebc46e13cee",
        "destination": "diffusion_models/Wan2_2-I2V_AniSoraV3_2_LOW_14B_fp8_e4m3fn_scaled_KJ.safetensors",
    },

    # Shared Wan components
    "umt5-xxl": {
        "repo_id": "Comfy-Org/Wan_2.1_ComfyUI_repackaged",
        "filename": "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "revision": "123acf1cc74bccbb9bfff8ac1ee72edc08c2341d",
        "destination": "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    },
    "clip-vision-h": {
        "repo_id": "Comfy-Org/Wan_2.1_ComfyUI_repackaged",
        "filename": "split_files/clip_vision/clip_vision_h.safetensors",
        "revision": "123acf1cc74bccbb9bfff8ac1ee72edc08c2341d",
        "destination": "clip_vision/clip_vision_h.safetensors",
    },
    "wan-vae": {
        "repo_id": "Comfy-Org/Wan_2.1_ComfyUI_repackaged",
        "filename": "split_files/vae/wan_2.1_vae.safetensors",
        "revision": "123acf1cc74bccbb9bfff8ac1ee72edc08c2341d",
        "destination": "vae/wan_2.1_vae.safetensors",
    },
    "wan-vae-bf16": {
        "repo_id": "Kijai/WanVideo_comfy",
        "filename": "Wan2_1_VAE_bf16.safetensors",
        "revision": "8260d429d19fd7a72304cad059160b95d843913f",
        "destination": "vae/Wan2_1_VAE_bf16.safetensors",
    },

    # Animate: SCAIL 2
    "scail2": {
        "repo_id": "Comfy-Org/SCAIL-2",
        "filename": "diffusion_models/wan2.1_14B_SCAIL_2_fp16.safetensors",
        "revision": "fe3c728bc793ba21ca674688f822afb709ad44fb",
        "destination": "diffusion_models/wan2.1_14B_SCAIL_2_fp16.safetensors",
    },
    "scail2-dpo": {
        "repo_id": "Comfy-Org/SCAIL-2",
        "filename": "loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors",
        "revision": "fe3c728bc793ba21ca674688f822afb709ad44fb",
        "destination": "loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors",
    },
    "lightx2v": {
        "repo_id": "Kijai/WanVideo_comfy",
        "filename": "Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
        "revision": "8260d429d19fd7a72304cad059160b95d843913f",
        "destination": "loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
    },

    # Background removal: BiRefNet ToonOut
    "toonout": {
        "repo_id": "1038lab/BiRefNet",
        "filename": "BiRefNet_toonout.safetensors",
        "revision": "4d000788a9698c7f8d67c8c6ce2b40c768f5b909",
        "destination": "RMBG/BiRefNet/BiRefNet_toonout.safetensors",
    },
    "birefnet-code": {
        "repo_id": "1038lab/BiRefNet",
        "filename": "birefnet.py",
        "revision": "4d000788a9698c7f8d67c8c6ce2b40c768f5b909",
        "destination": "RMBG/BiRefNet/birefnet.py",
    },
    "birefnet-config-code": {
        "repo_id": "1038lab/BiRefNet",
        "filename": "BiRefNet_config.py",
        "revision": "4d000788a9698c7f8d67c8c6ce2b40c768f5b909",
        "destination": "RMBG/BiRefNet/BiRefNet_config.py",
    },
    "birefnet-config": {
        "repo_id": "1038lab/BiRefNet",
        "filename": "config.json",
        "revision": "4d000788a9698c7f8d67c8c6ce2b40c768f5b909",
        "destination": "RMBG/BiRefNet/config.json",
    },
}

def download_model(
    repo_id: str,
    filename: str,
    *,
    revision: str,
    destination: Path,
) -> Path:
    cached = Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            revision=revision
        )
    ).resolve()
    destination = destination.expanduser().absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        if destination.resolve() == cached:
            return destination
        destination.unlink()
    elif destination.exists():
        raise FileExistsError(
            f"Model file already exists: {destination}"
        )
    destination.symlink_to(cached)
    return destination