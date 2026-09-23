"""Native model workers. Each invocation is a separate process to release VRAM.

FLUX uses Diffusers; AniSora and SCAIL2 use pinned upstream Python modules.
No Comfy imports, server, nodes, workflow executor, or network inference.
"""
import copy
import json
from pathlib import Path
import sys
import time
import logging

from PIL import Image, ImageFilter, ImageOps
from sprute_lib.media import (ORDER, cut_grid, gray, pad, read_frames, save_frames, strip, webp)


def tensor_frames(video):
    """Native Wan output C,T,H,W in [-1,1] -> RGB Pillow frames."""
    array = ((video.detach().float().cpu().clamp(-1, 1) + 1) * 127.5).round().byte()
    return [Image.fromarray(a.numpy()) for a in array.permute(1, 2, 3, 0)]


class ToonOut:
    def __init__(self, models, device='cuda'):
        import torch
        from transformers import AutoConfig, AutoModelForImageSegmentation
        from torchvision import transforms
        self.torch, self.device = torch, device
        self.dtype = torch.float16 if device == 'cuda' else torch.float32
        config = AutoConfig.from_pretrained(str(models/'birefnet'), trust_remote_code=True,
                                            local_files_only=True)
        self.model = AutoModelForImageSegmentation.from_config(config, trust_remote_code=True)
        weights = models/'toonout'
        if weights.resolve().suffix == '.safetensors':
            from safetensors.torch import load_file
            state = load_file(str(weights))
        else:
            state = torch.load(weights, map_location='cpu', weights_only=True)
        state = {k.removeprefix('module.').removeprefix('_orig_mod.'): v for k, v in state.items()}
        self.model.load_state_dict(state, strict=True)
        self.model.eval().to(device=device, dtype=self.dtype)
        self.transform = transforms.Compose([transforms.ToTensor(),
            transforms.Normalize([.485, .456, .406], [.229, .224, .225])])

    def __call__(self, image, resolution=512, blur=0, offset=0):
        import numpy as np
        import cv2
        src = image.convert('RGB')
        tensor = self.transform(src.resize((resolution, resolution), Image.Resampling.BILINEAR))
        with self.torch.inference_mode():
            pred = self.model(tensor.unsqueeze(0).to(self.device, self.dtype))[-1].sigmoid()[0, 0]
        alpha = Image.fromarray((pred.float().cpu().numpy()*255).round().astype('uint8'))
        alpha = alpha.resize(src.size, Image.Resampling.BILINEAR)
        for _ in range(abs(offset)):
            alpha = alpha.filter(ImageFilter.MaxFilter(3) if offset > 0 else ImageFilter.MinFilter(3))
        if blur:
            alpha = alpha.filter(ImageFilter.GaussianBlur(blur))
        # Fast foreground colour estimation removes grey fringes at soft edges.
        rgb = np.asarray(src, dtype=np.float32)/255
        a = np.asarray(alpha, dtype=np.float32)[:, :, None]/255
        foreground, background = rgb, rgb
        for radius in (90, 6):
            ba = cv2.blur(a, (radius, radius))[:, :, None]
            bf = cv2.blur(foreground*a, (radius, radius))/(ba+1e-5)
            background = cv2.blur(background*(1-a), (radius, radius))/(1-ba+1e-5)
            foreground = np.clip(bf+a*(rgb-a*bf-(1-a)*background), 0, 1)
        result = Image.fromarray((foreground*255).round().astype('uint8')).convert('RGBA')
        result.putalpha(alpha)
        return result


def generate(job, models, out):
    import torch
    from diffusers import FluxFillPipeline
    source = Image.open(job['template']).convert('RGBA')
    original_size = source.size
    # FLUX packs 2x2 latent patches. Pad rather than silently resize/crop the template.
    packed_size = tuple(((v+15)//16)*16 for v in source.size)
    if packed_size != source.size:
        canvas = Image.new('RGBA', packed_size, (128,128,128,255))
        canvas.paste(source, (0,0))
        source = canvas
    mask = ImageOps.invert(source.getchannel('A'))
    if mask.getextrema()[1] == 0:
        raise ValueError('Fill template needs a transparent region to generate into')
    # Reference examples are visible; alpha=0 is the region FLUX should fill.
    flux = models/'flux'
    components = {}
    # Reuse original BFL checkpoints through symlinks; convert keys in memory only.
    if (flux/'transformer/original.safetensors').is_file():
        from diffusers import FluxTransformer2DModel, AutoencoderKL
        for name, cls in [('transformer', FluxTransformer2DModel), ('vae', AutoencoderKL)]:
            components[name] = cls.from_single_file(
                str(flux/name/'original.safetensors'), config=str(flux), subfolder=name,
                torch_dtype=torch.bfloat16, local_files_only=True)
    pipe = FluxFillPipeline.from_pretrained(str(flux), torch_dtype=torch.bfloat16,
                                            local_files_only=True, **components)
    pipe.enable_model_cpu_offload()
    result = pipe(prompt=job['prompt'], image=source.convert('RGB'), mask_image=mask,
                  width=source.width, height=source.height,
                  num_inference_steps=job['steps'], guidance_scale=job['guidance'],
                  generator=torch.Generator('cpu').manual_seed(job['seed'])).images[0]
    result = result.crop((0, 0, *original_size))
    result.save(out/'template-result.png')
    # The original SpriteDX template is 4 columns x 2 rows, target index 6.
    w, h = result.size
    x, y = job['cell_index'] % 4, job['cell_index'] // 4
    crop = result.crop((round(x*w/4), round(y*h/2), round((x+1)*w/4), round((y+1)*h/2)))
    crop.save(out/'reference-rgb.png')
    del pipe
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    matte = ToonOut(models)
    reference = matte(crop.resize((1024, 1024), Image.Resampling.LANCZOS), 1024, blur=2, offset=-1)
    pad(reference, (640, 640)).save(out/'reference.png')


def import_wan(models, name):
    source = models/'_sources'/name
    if name == 'anisora':
        source = source/'anisoraV3.2'
    sys.path.insert(0, str(source))
    import wan
    from sprute_lib.attention import install_if_needed
    print('Attention backend:', install_if_needed(), flush=True)
    return wan, source


def turntable(job, models, out):
    import torch
    if job.get('precision') == 'fp8':
        from sprute_lib.fp8 import check_fp8_backend
        check_fp8_backend('cuda')
        if not (models/'anisora/scaled-fp8.json').is_file():
            raise ValueError('FP8 turntable requires the linked scaled-FP8 AniSora layout')
    wan, _ = import_wan(models, 'anisora')
    cfg = copy.deepcopy(wan.configs.WAN_CONFIGS['i2v-A14B'])
    from sprute_lib.loading import linked_anisora
    with linked_anisora(sys.modules[wan.WanI2V.__module__],
                        (models/'anisora/scaled-fp8.json').is_file(),
                        precision=job.get('precision', 'bf16')):
        pipe = wan.WanI2V(config=cfg, checkpoint_dir=str(models/'anisora'),
            checkpoint_dir_lowname='low_noise_model', checkpoint_dir_highname='high_noise_model',
            t5_cpu=True, convert_model_dtype=True)
    image = gray(pad(Image.open(job['image']), (job['size'], job['size'])))
    image.save(out/'input.png')
    result = pipe.generate(job['prompt'], [image], [0.0], max_area=job['size']**2,
        frame_num=81, shift=5, sample_solver='unipc', sampling_steps=job['steps'],
        guide_scale=(1.0, 1.0), n_prompt=job['negative'], seed=job['seed'], offload_model=True)
    frames = tensor_frames(result)
    if len(frames) != 81:
        raise ValueError(f'Expected 81 turntable frames, got {len(frames)}')
    save_frames(frames, out/'frames')
    webp(frames, out/'turntable.webp', fps=24)
    del pipe, result
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    matte = ToonOut(models)
    # Matches demo's 0,10,...70 selection followed by 0,7,6,...1 reorder.
    indices = [0, 70, 60, 50, 40, 30, 20, 10]
    cells = []
    for direction, index in zip(ORDER, indices):
        frame = frames[index]
        width = round(frame.height*320/512)
        x = (frame.width-width)//2
        cell = matte(frame.crop((x, 0, x+width, frame.height)))
        cell.save(out/f'{direction}.png')
        cells.append(cell)
    strip(cells).save(out/'standing.png')
    (out/'selection.json').write_text(json.dumps(dict(order=ORDER, indices=indices,
        note='Approximate directions. Generated angular velocity is not guaranteed.'), indent=2))


def animate(job, models, out):
    import torch
    import numpy as np
    wan, source = import_wan(models, 'scail2')
    cfg = copy.deepcopy(wan.configs.SCAIL_CONFIGS['SCAIL-14B'])
    # Set absolute paths; all files are supplied locally by the model manager.
    aux = models/'scail_aux'
    cfg.t5_checkpoint = str(aux/'umt5-xxl/models_t5_umt5-xxl-enc-bf16.pth')
    cfg.t5_tokenizer = str(aux/'umt5-xxl')
    cfg.vae_checkpoint = str(aux/'Wan2.1_VAE.pth')
    cfg.clip_checkpoint = str(aux/'models_clip_open-clip-xlm-roberta-large-vit-huge-14-onlyvisual.pth')
    cfg.clip_tokenizer = str(models/'xlm_tokenizer')
    from sprute_lib.loading import low_memory_scail
    from sprute_lib.umt5 import linked_text_encoder
    import wan.scail as scail_module
    text_checkpoint = job.get('text_encoder_fp8')
    if text_checkpoint:
        from sprute_lib.fp8 import check_fp8_backend
        check_fp8_backend('cuda')
    logging.info('Loading native SCAIL2: T5, VAE, CLIP, then diffusion weights')
    with low_memory_scail(scail_module), linked_text_encoder(scail_module, text_checkpoint):
        pipe = wan.SCAIL2Pipeline(config=cfg, checkpoint_dir=str(aux),
            scail_safetensors_path=str(models/'scail_model'),
            scail_config_path=str(source/'configs/config-14b.json'), t5_cpu=not bool(text_checkpoint),
            lora_path=str(models/'dpo'), lora_alpha=1.0)
    pipe.fuse_lora(str(models/'lightx2v'), 0.8)
    if job.get('precision') == 'fp8':
        from sprute_lib.fp8 import check_fp8_backend, quantize_linears
        check_fp8_backend('cuda')
        count = quantize_linears(pipe.model)
        logging.info('SCAIL2: quantized %d linear layers to FP8 after LoRA fusion', count)
    def tensor(image):
        return torch.from_numpy(np.array(image.convert('RGB')).copy()).permute(2,0,1).float()/127.5-1
    prepared = Path(job['prepared'])
    info = json.loads((prepared/'segments.json').read_text())
    pose = torch.stack([tensor(f) for f in read_frames(prepared/'driver')]).to('cuda')
    masks = torch.stack([tensor(f) for f in read_frames(prepared/'driver-mask')], dim=1).to('cuda')
    result = pipe.generate(job['prompt'], tensor(Image.open(prepared/'reference.png')).to('cuda'),
        ref_mask_img=tensor(Image.open(prepared/'reference-mask.png')).to('cuda'),
        pose_video=pose, driving_mask_video=masks, replace_flag=info['replacement'],
        segment_len=info['inference_frames'], segment_overlap=5, shift=5,
        sample_solver='unipc', sampling_steps=job['steps'], guide_scale=1.0,
        n_prompt='', seed=job['seed'], offload_model=True)
    frames = tensor_frames(result)
    if len(frames) < info['frames']:
        raise ValueError('SCAIL produced fewer frames than the state manifest requires')
    frames = frames[:info['frames']]
    save_frames(frames, out/'frames')
    webp(frames, out/'animation-rgb.webp', fps=info['fps'])


def export(job, models, out):
    info = json.loads(Path(job['segments']).read_text())
    frames = read_frames(job['video'])
    if len(frames) < info['frames']:
        raise ValueError('Output sequence is shorter than the state manifest')
    directions = cut_grid(frames[:info['frames']])
    matte = ToonOut(models)
    # Crop FIRST: ToonOut sees one character at a time, as in our successful pipeline.
    for state in info['segments']:
        dest = out/state['state']
        dest.mkdir(parents=True, exist_ok=True)
        start, count = state['start'], state['count']
        alpha = {}
        for direction in ORDER:
            alpha[direction] = [matte(f) for f in directions[direction][start:start+count]]
            save_frames(alpha[direction], dest/direction)
            webp(alpha[direction], dest/f'{direction}.webp', info['fps'], job['quality'])
        horizontal = [strip([alpha[d][i] for d in ORDER]) for i in range(count)]
        webp(horizontal, dest/'horizontal.webp', info['fps'], job['quality'])
    (out/'animation.json').write_text(json.dumps({**info,
        'loop_policy': 'Driver boundaries, not automatically verified generated-motion loops.'}, indent=2))


def main():
    import torch
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    job = json.loads(Path(sys.argv[1]).read_text())
    if not torch.cuda.is_available():
        raise RuntimeError('Native inference currently requires an NVIDIA CUDA GPU')
    models, out = Path(job['models']), Path(job['out'])
    torch.cuda.reset_peak_memory_stats()
    start = time.monotonic()
    try:
        with torch.inference_mode():
            globals()[job['stage']](job, models, out)
    finally:
        (out/'performance.json').write_text(json.dumps(dict(
            seconds=time.monotonic()-start,
            peak_torch_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_torch_reserved_bytes=torch.cuda.max_memory_reserved(),
            scope='This worker process only; not whole-device peak VRAM'), indent=2))

if __name__ == '__main__':
    main()
