"""Explicit, pinned model downloads and local directory/file links. No Comfy runtime."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS = ROOT / 'models'
SOURCES = {
    'anisora': ('https://github.com/bilibili/Index-anisora.git',
                '6cdce3a17548d7ff0f2e05978469f134da25e68e'),
    'scail2': ('https://github.com/zai-org/SCAIL-2.git',
               '78fe19576bb06be96c2375e088574a262a300edb'),
}

# name: repo, immutable revision, patterns, subdirectory within snapshot
MODELS = {
    'scail_model': ('Comfy-Org/SCAIL-2', '3bd725f20edad6967a65792af3017e251a5bd853',
                    ['diffusion_models/wan2.1_14B_SCAIL_2_fp16.safetensors'],
                    'diffusion_models/wan2.1_14B_SCAIL_2_fp16.safetensors'),
    'dpo': ('Comfy-Org/SCAIL-2', '3bd725f20edad6967a65792af3017e251a5bd853',
             ['loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors'],
             'loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors'),
    'lightx2v': ('Kijai/WanVideo_comfy', '8260d429d19fd7a72304cad059160b95d843913f',
                 ['Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'],
                 'Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'),
    'flux': ('black-forest-labs/FLUX.1-Fill-dev',
             '358293da0354175698b67ec8299acf928313a78a',
             ['model_index.json', 'scheduler/*', 'text_encoder/*', 'text_encoder_2/*',
              'tokenizer/*', 'tokenizer_2/*', 'transformer/*', 'vae/*'], ''),
    'anisora': ('IndexTeam/Index-anisora', 'b134a8e677e4b22269827af7d596a4f2d9d3430a',
                ['V3.2/*'], 'V3.2'),
    'scail_aux': ('zai-org/SCAIL-2', '150cc0ca4e98e50e60b9295dacde39442fdccab2',
                  ['Wan2.1_VAE.pth', 'umt5-xxl/*',
                   'models_clip_open-clip-xlm-roberta-large-vit-huge-14-onlyvisual.pth'], ''),
    'xlm_tokenizer': ('FacebookAI/xlm-roberta-large',
                      'c23d21b0620b635a76227c604d44e43a9f0ee389',
                      ['tokenizer*', 'sentencepiece.bpe.model', 'config.json'], ''),
    'birefnet': ('ZhengPeng7/BiRefNet', 'e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4',
                 ['*.py', 'config.json'], ''),
    'toonout': ('joelseytre/toonout', 'cbf720eca394edcde66b861a8a8c20fbabe9c748',
                ['birefnet_finetuned_toonout.pth'], 'birefnet_finetuned_toonout.pth'),
}
STAGES = {
    'generate': ['flux', 'birefnet', 'toonout'],
    'turntable': ['anisora', 'birefnet', 'toonout'],
    'animate': ['scail_aux', 'scail_model', 'dpo', 'lightx2v', 'xlm_tokenizer', 'birefnet', 'toonout'],
    'matte': ['birefnet', 'toonout'],
}
REQUIRED_FILES = {
    'flux': ['model_index.json', 'transformer/config.json', 'vae/config.json',
             'tokenizer/tokenizer_config.json', 'tokenizer_2/tokenizer_config.json'],
    'anisora': ['high_noise_model/diffusion_pytorch_model.safetensors',
                'low_noise_model/diffusion_pytorch_model.safetensors',
                'models_t5_umt5-xxl-enc-bf16.pth', 'Wan2.1_VAE.pth',
                'google/umt5-xxl/tokenizer_config.json'],
    'scail_aux': ['umt5-xxl/models_t5_umt5-xxl-enc-bf16.pth', 'Wan2.1_VAE.pth',
                  'models_clip_open-clip-xlm-roberta-large-vit-huge-14-onlyvisual.pth'],
    'birefnet': ['config.json', 'birefnet.py', 'BiRefNet_config.py'],
    'xlm_tokenizer': ['tokenizer_config.json'],
}

def link(root, name, source):
    if name not in MODELS:
        raise ValueError(f'Unknown model {name}; choose {", ".join(MODELS)}')
    source = Path(source).expanduser().resolve(strict=True)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / name
    if dest.exists() or dest.is_symlink():
        if dest.resolve() == source:
            return dest
        raise FileExistsError(f'{dest} already exists; refusing to replace it')
    dest.symlink_to(source, target_is_directory=source.is_dir())
    return dest

def setup_sources(root):
    for name, (url, revision) in SOURCES.items():
        dest = root / '_sources' / name
        if not dest.exists():
            dest.mkdir(parents=True)
            subprocess.run(['git', 'init', str(dest)], check=True)
            subprocess.run(['git', '-C', str(dest), 'remote', 'add', 'origin', url], check=True)
            subprocess.run(['git', '-C', str(dest), 'fetch', '--depth', '1', 'origin', revision], check=True)
            subprocess.run(['git', '-C', str(dest), 'checkout', '--detach', 'FETCH_HEAD'], check=True)
        actual = subprocess.check_output(['git', '-C', str(dest), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != revision:
            raise ValueError(f'{dest}: expected {revision}, got {actual}; not modifying existing source')

def download(root, stage):
    from huggingface_hub import snapshot_download
    names = list(MODELS) if stage == 'all' else STAGES[stage]
    for name in names:
        if (root / name).exists():
            print(f'Using {root / name}', flush=True)
            continue
        repo, revision, patterns, subdir = MODELS[name]
        print(f'Downloading {name} from {repo}@{revision}', flush=True)
        cached = snapshot_download(repo_id=repo, revision=revision, allow_patterns=patterns)
        link(root, name, Path(cached) / subdir)
    (root / 'sources.json').write_text(json.dumps(MODELS, indent=2))

def require(root, stage):
    missing = [name for name in STAGES[stage] if not (root / name).exists()]
    if missing:
        raise FileNotFoundError(f'Missing models: {", ".join(missing)}. Run models download --stage {stage}, or models link.')
    for name in STAGES[stage]:
        path = root/name
        if name in REQUIRED_FILES:
            absent = [f for f in REQUIRED_FILES[name] if not (path/f).is_file()]
            if absent:
                raise FileNotFoundError(f'{path} has the wrong layout or is incomplete: {absent}')
        elif not path.is_file():
            raise ValueError(f'{path} must point to a weight file, not a directory')
    if stage in ('turntable', 'animate'):
        name = 'anisora' if stage == 'turntable' else 'scail2'
        path = root / '_sources' / name
        if not path.exists():
            raise FileNotFoundError('Native source missing. Run: sprute.py models setup')
        revision = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
        if revision != SOURCES[name][1]:
            raise ValueError(f'Unexpected source revision for {name}: {revision}')
