"""Headless local Qwen edit using installed Comfy modules, no server/API calls."""
from pathlib import Path
import sys,os,json,time,traceback,gc,argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--job',type=Path,required=True)
args=parser.parse_args()
job_path=args.job.resolve();job=json.loads(job_path.read_text());base=job_path.parent
required=['reference','comfyRoot','diffusionModels','output','prompt']
for key in required:
 if not isinstance(job.get(key),str) or not job[key].strip():raise ValueError(f'Missing {key}')
def path(key):return (base/job[key]).resolve()
reference=path('reference');comfy_root=path('comfyRoot');models=path('diffusionModels');root=path('output')
if not reference.is_file() or not comfy_root.is_dir() or not models.is_dir():raise ValueError('Missing local input/runtime/model directory')
width=job.get('width',1024);height=job.get('height',1024);seed=job.get('seed',42)
if any(type(v) is not int or v<256 or v>1024 or v%16 for v in [width,height]):raise ValueError('Dimensions must be multiples of16 from256 to1024')
if type(seed) is not int or not 0<=seed<2**32:raise ValueError('Invalid seed')
root.mkdir(exist_ok=False)
(root/'job.json').write_text(json.dumps(job,indent=2))
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import torch
torch.set_grad_enabled(False)
os.chdir(comfy_root);sys.path.insert(0,str(comfy_root))
total=torch.cuda.get_device_properties(0).total_memory;budget=28*1024**3
budget=min(budget,total)
torch.cuda.set_per_process_memory_fraction(budget/total,0)
sys.argv=[sys.argv[0],'--lowvram','--reserve-vram',str((total-budget)/1024**3)]
import comfy.options
comfy.options.enable_args_parsing()
import nodes,comfy.model_management as mm
import folder_paths
folder_paths.folder_names_and_paths['diffusion_models']=([str(models)],folder_paths.supported_pt_extensions)
from comfy_extras.nodes_qwen import TextEncodeQwenImageEditPlus
from comfy_extras.nodes_model_advanced import ModelSamplingAuraFlow
from comfy_extras.nodes_sd3 import EmptySD3LatentImage
from PIL import Image
import numpy as np
start=time.time();receipt={'gradEnabled':torch.is_grad_enabled(),'status':'running','pid':os.getpid(),'budgetBytes':budget,'physicalBytes':total,'stages':[]}
def save(stage):
 torch.cuda.synchronize();receipt['stages'].append({'stage':stage,'seconds':time.time()-start,'allocated':torch.cuda.memory_allocated(),'reserved':torch.cuda.memory_reserved(),'peakReserved':torch.cuda.max_memory_reserved()})
 (root/'state.json').write_text(json.dumps(receipt,indent=2));print(stage,flush=True)
try:
 save('starting')
 torch.cuda.reset_peak_memory_stats()
 image=torch.from_numpy(np.array(Image.open(reference).convert('RGB')).astype(np.float32)/255)[None]
 guide=torch.from_numpy(np.array(Image.open(path('guide')).convert('RGB')).astype(np.float32)/255)[None] if job.get('guide') else None
 vae=nodes.VAELoader().load_vae('qwen_image_vae.safetensors')[0]
 clip=nodes.CLIPLoader().load_clip('qwen_2.5_vl_7b_fp8_scaled.safetensors','qwen_image')[0]
 prompt=job['prompt']
 positive=TextEncodeQwenImageEditPlus.execute(clip,prompt,vae,image,guide)[0]
 negative=TextEncodeQwenImageEditPlus.execute(clip,'',vae,image,guide)[0]
 save('encoded');del clip;mm.unload_all_models();gc.collect();mm.soft_empty_cache()
 model=nodes.UNETLoader().load_unet('qwen_image_edit_2509_fp8_e4m3fn.safetensors','default')[0]
 model=ModelSamplingAuraFlow().patch_aura(model,3)[0]
 latent=EmptySD3LatentImage.execute(width,height,1)[0]
 result=nodes.KSampler().sample(model,seed,20,4,'euler','simple',positive,negative,latent)[0]
 torch.save(result['samples'].detach().cpu(),root/'latent.pt')
 save('sampled');del model;mm.unload_all_models();gc.collect();mm.soft_empty_cache()
 pixels=vae.decode(result['samples']).detach().cpu().numpy()
 while pixels.ndim>3 and pixels.shape[0]==1:
  pixels=pixels[0]
 if pixels.shape!=(height,width,3):raise ValueError(f'Unexpected decoded shape: {pixels.shape}')
 Image.fromarray((pixels.clip(0,1)*255).astype(np.uint8)).save(root/'result.png')
 receipt['status']='complete';save('decoded')
except BaseException:
 receipt.update(status='failed',error=traceback.format_exc());(root/'state.json').write_text(json.dumps(receipt,indent=2));raise
