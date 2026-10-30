"""Image -> mesh GLB with ComfyUI's native TRELLIS.2 nodes, on a running ComfyUI server.

Wiring follows Comfy-Org's "Pixal3D & TRELLIS.2: Image to Model" template (TRELLIS.2 branch),
rewritten for the 0.37 node schemas. Shape only, decimated to --faces; --textured also bakes TRELLIS's own colour
into a UV texture (for a clean, evenly lit drawing, such as a Codex T-pose; a cel-shaded sprite bakes badly).

python trellis_shape.py IMAGE PREFIX [--textured] [--unet trellis_2_bf16.safetensors] [--server http://127.0.0.1:8188]
"""
import argparse, json, time, urllib.request, uuid
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("image"); ap.add_argument("prefix")
ap.add_argument("--unet", default="trellis_2_bf16.safetensors")
ap.add_argument("--server", default="http://127.0.0.1:8188")
ap.add_argument("--faces", type=int, default=200000)
ap.add_argument("--low-faces", type=int, default=3000)
ap.add_argument("--seed", type=int, default=56)
ap.add_argument("--textured", action="store_true")
a = ap.parse_args()

def upload(path):
    boundary = uuid.uuid4().hex; data = Path(path).read_bytes()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{Path(path).name}\"\r\n"
            f"Content-Type: image/png\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(a.server + "/upload/image", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.load(urllib.request.urlopen(req))["name"]

def ks(model, seed, steps, cfg, sched, stage):
    return {"class_type": "KSampler", "inputs": {"model": model, "seed": seed, "steps": steps, "cfg": cfg,
            "sampler_name": "euler", "scheduler": sched, "positive": [stage, 0], "negative": [stage, 1],
            "latent_image": [stage, 2], "denoise": 1.0}}

g = {
 "img": {"class_type": "LoadImage", "inputs": {"image": upload(a.image)}},
 "bgm": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}},
 "bg": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["bgm", 0], "image": ["img", 0]}},
 "crop": {"class_type": "ImageCropToMask", "inputs": {"images": ["img", 0], "masks": ["bg", 0], "width": 1024,
          "height": 1024, "pad_factor": 1.0, "grow_mask": 0, "background": "#000000"}},
 "dino": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "dino_v3_vit_l.safetensors"}},
 "cond": {"class_type": "Trellis2Conditioning", "inputs": {"clip_vision_model": ["dino", 0], "image": ["crop", 0]}},
 "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": a.unet, "weight_dtype": "default"}},
 # structure model: CFGOverride -> RescaleCFG 0.7 -> shift 5
 "cfgA": {"class_type": "CFGOverride", "inputs": {"model": ["unet", 0], "cfg": 1, "start_percent": 0.667, "end_percent": 1}},
 "rsA": {"class_type": "RescaleCFG", "inputs": {"model": ["cfgA", 0], "multiplier": 0.7}},
 "msA": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["rsA", 0], "shift": 5}},
 # shape model: CFGOverride -> RescaleCFG 0.5
 "cfgB": {"class_type": "CFGOverride", "inputs": {"model": ["unet", 0], "cfg": 1, "start_percent": 0.769, "end_percent": 1}},
 "rsB": {"class_type": "RescaleCFG", "inputs": {"model": ["cfgB", 0], "multiplier": 0.5}},
 "svae": {"class_type": "VAELoader", "inputs": {"vae_name": "trellis_2_shape_vae_bf16.safetensors"}},
 "tvae": {"class_type": "VAELoader", "inputs": {"vae_name": "trellis_2_texture_vae_bf16.safetensors"}},
 "empty": {"class_type": "EmptyTrellis2LatentStructure", "inputs": {"batch_size": 1}},
 "ks_struct": {"class_type": "KSampler", "inputs": {"model": ["msA", 0], "seed": a.seed, "steps": 12, "cfg": 7.5,
               "sampler_name": "euler", "scheduler": "normal", "positive": ["cond", 0], "negative": ["cond", 1],
               "latent_image": ["empty", 0], "denoise": 1.0}},
 "struct": {"class_type": "VaeDecodeStructureTrellis2", "inputs": {"samples": ["ks_struct", 0], "vae": ["svae", 0], "resolution": "32"}},
 "shape_st": {"class_type": "Trellis2ShapeStage", "inputs": {"positive": ["cond", 0], "negative": ["cond", 1], "voxel": ["struct", 0]}},
 "ks_shape": ks(["rsB", 0], 42, 20, 7.5, "normal", "shape_st"),
 "up_st": {"class_type": "Trellis2UpsampleStage", "inputs": {"positive": ["shape_st", 0], "negative": ["shape_st", 1],
           "shape_latent": ["ks_shape", 0], "vae": ["svae", 0], "target_resolution": 1536}},
 "ks_up": ks(["rsB", 0], 42, 12, 7.5, "simple", "up_st"),
 "shape": {"class_type": "VaeDecodeShapeTrellis", "inputs": {"samples": ["ks_up", 0], "vae": ["svae", 0]}},
 "tex_st": {"class_type": "Trellis2TextureStage", "inputs": {"positive": ["up_st", 0], "negative": ["up_st", 1], "shape_latent": ["ks_up", 0]}},
 "ks_tex": ks(["unet", 0], 43, 12, 1, "normal", "tex_st"),
 "tex": {"class_type": "VaeDecodeTextureTrellis", "inputs": {"samples": ["ks_tex", 0], "vae": ["tvae", 0], "shape_subdivides": ["shape", 1]}},
 "remesh": {"class_type": "RemeshMesh", "inputs": {"mesh": ["shape", 0], "resolution": 768, "sign_mode": "udf",
            "sign_mode.qef": False, "sign_mode.drop_inverted_components": False, "sign_mode.drop_enclosed_components": False,
            "band": 1.0, "project_back": 0.0, "fix_poles": False, "smooth_iters": 0, "drop_small_components": 0.01,
            "precluster_max_verts": 20000000}},
}


g["dec"] = {"class_type": "DecimateMesh", "inputs": {"mesh": ["remesh", 0], "target_face_count": a.faces, "placement_mode": "midpoint"}}
if a.textured:
    g["smooth"] = {"class_type": "MeshSmoothNormals", "inputs": {"mesh": ["dec", 0], "crease_angle": 180}}
    g["uv"] = {"class_type": "UnwrapMesh", "inputs": {"mesh": ["smooth", 0], "segmenter": "pec", "resolution": 2048, "padding": 2, "weld_distance": 0.0002}}
    g["bake"] = {"class_type": "BakeTextureFromVoxel", "inputs": {"mesh": ["uv", 0], "voxel_colors": ["tex", 0], "texture_size": 2048, "reference_mesh": ["shape", 0]}}
    g["apply"] = {"class_type": "ApplyTextureToMesh", "inputs": {"mesh": ["uv", 0], "base_color": ["bake", 0], "metallic": ["bake", 1], "roughness": ["bake", 2]}}
    g["save"] = {"class_type": "SaveGLB", "inputs": {"mesh": ["apply", 0], "filename_prefix": f"3d/{a.prefix}_dense"}}
else:
    # Shape only: the paint comes from projecting the design (tools/render3d/paint_rig.py), not from TRELLIS's texture.
    for k in ("tex_st", "ks_tex", "tex", "tvae"): g.pop(k)
    g["save"] = {"class_type": "SaveGLB", "inputs": {"mesh": ["dec", 0], "filename_prefix": f"3d/{a.prefix}_shape"}}


t0 = time.time()
pid = json.load(urllib.request.urlopen(urllib.request.Request(a.server + "/prompt",
      data=json.dumps({"prompt": g, "client_id": "sprute-3d"}).encode(), headers={"Content-Type": "application/json"})))["prompt_id"]
print("queued", pid, flush=True)
while True:
    time.sleep(5)
    h = json.load(urllib.request.urlopen(f"{a.server}/history/{pid}"))
    if pid in h:
        st = h[pid]["status"]
        print(json.dumps({"status": st.get("status_str"), "seconds": round(time.time() - t0)}))
        if st.get("status_str") != "success":
            print(json.dumps(st.get("messages"))[-3000:])
        for nid, out in h[pid]["outputs"].items():
            for k, v in out.items():
                for f in v if isinstance(v, list) else []:
                    if isinstance(f, dict) and "filename" in f: print(nid, f.get("subfolder"), f["filename"])
        break
