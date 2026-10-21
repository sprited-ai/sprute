"""Sprute nodes for ComfyUI: render a motion on Template-kun into a driving video, and arrange the eight directions."""
import hashlib
from pathlib import Path

import comfy.model_management
import torch
import folder_paths

from . import kimodo, layout, motion_file, renderer, retarget

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "assets" / "template-kun" / "template-kun.glb"
MOTIONS = ROOT / "motions"
BUNDLED = "sprute/"


def motions():
    """Bundled motions first, then GLB files in ComfyUI's input folder."""
    bundled = sorted(BUNDLED + path.stem for path in MOTIONS.glob("*.glb"))
    folder = Path(folder_paths.get_input_directory())
    return bundled + sorted(str(path.relative_to(folder)) for path in folder.rglob("*.glb"))


def motion_path(name: str) -> Path:
    if name.startswith(BUNDLED):
        return MOTIONS / f"{name.removeprefix(BUNDLED)}.glb"
    return Path(folder_paths.get_annotated_filepath(name))


class SpruteLoadMotion:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "motion": (motions(), {"tooltip": "A bundled motion, or an animated GLB in ComfyUI's input folder."}),
            "animation": ("STRING", {"default": "", "tooltip": "Which animation in the GLB, by name. Empty picks the first."}),
        }}

    RETURN_TYPES = ("SPRUTE_MOTION",)
    RETURN_NAMES = ("motion",)
    FUNCTION = "load"
    CATEGORY = "Sprute"
    DESCRIPTION = "Loads a motion. A GLB with another character's rig is retargeted onto Template-kun."

    def load(self, motion, animation):
        path = motion_path(motion)
        document, _ = motion_file.load(path)
        if document["asset"].get("generator") == "sprute-kimodo":
            return (kimodo.load_motion(path, MODEL),)
        if document["asset"].get("generator") == "sprute":
            return (motion_file.read(path),)
        return (retarget.retarget(path, animation.strip(), MODEL),)

    @classmethod
    def IS_CHANGED(cls, motion, animation):
        # By content, like Load Image: the same file gives the same saved workflow wherever it is copied.
        return f"{hashlib.sha256(motion_path(motion).read_bytes()).hexdigest()}:{animation}"


class SpruteRenderDrivingVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "motion": ("SPRUTE_MOTION",),
            "frames": ("INT", {"default": 0, "min": 0, "max": 1000, "tooltip": "0 saves the complete source clip (one cycle for looping motions)."}),
            "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 1.0}),
            "cell_width": ("INT", {"default": 256, "min": 32, "max": 1024, "step": 32}),
            "cell_height": ("INT", {"default": 256, "min": 32, "max": 1024, "step": 32}),
        }}

    RETURN_TYPES = ("IMAGE", "MASK", "INT", "BOOLEAN", "FLOAT")
    RETURN_NAMES = ("image", "mask", "loop_frames", "loop", "fps")
    FUNCTION = "render"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Renders Template-kun performing the motion in eight directions, as a strip like a sprute animation. "
                   "IMAGE and MASK match what Load Image gives for a transparent driving video.")

    def render(self, motion, frames, fps, cell_width, cell_height):
        import math
        period = len(motion[4]) / motion[1]
        intervals = period * fps
        cycle = round(intervals) if abs(intervals - round(intervals)) < 1e-6 else None
        if frames == 0:
            frames = max(1, math.ceil(len(motion[4]) / motion[1] * fps - 1e-6))
        device = comfy.model_management.get_torch_device()
        key = (str(device), MODEL.stat().st_mtime_ns)
        if getattr(self, "_key", None) != key:
            self._model, self._key = renderer.Model(MODEL, device), key
        video = renderer.render(self._model, motion, frames, fps, cell_width, cell_height).cpu()
        return (video[..., :3], 1.0 - video[..., 3], (cycle or 0) if motion[2] else 0, bool(motion[2]), fps)


class SpruteSaveDrivingVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "loop_frames": ("INT", {"default": 0, "min": 0}),
                             "loop": ("BOOLEAN", {"default": False}),
                             "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0}),
                             "filename_prefix": ("STRING", {"default": "motion"})},
                "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}}

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Sprute"

    def save(self, images, loop_frames, loop, fps, filename_prefix, prompt=None, extra_pnginfo=None):
        import json
        import numpy as np
        from PIL import Image
        folder, name, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, folder_paths.get_output_directory(), images[0].shape[1], images[0].shape[0])
        frames = [Image.fromarray(np.clip(frame.cpu().numpy() * 255, 0, 255).astype(np.uint8)) for frame in images]
        metadata = Image.Exif()
        metadata[0x010E] = json.dumps({"sprute_motion_timing": {"version": 1, "loop": loop,
            "cycle_frames": loop_frames, "render_fps": fps, "stored_frames": len(frames)}})
        if prompt is not None:
            metadata[0x0110] = "prompt:" + json.dumps(prompt)
        if extra_pnginfo is not None and "workflow" in extra_pnginfo:
            metadata[0x010F] = "workflow:" + json.dumps(extra_pnginfo["workflow"])
        filename = f"{name}_{counter:05}_.webp"
        frames[0].save(Path(folder, filename), format="WEBP", save_all=True,
                       append_images=frames[1:], duration=int(1000 / fps),
                       loop=0 if loop else 1, lossless=True, method=4, exif=metadata)
        return {"ui": {"images": [{"filename": filename, "subfolder": subfolder, "type": "output"}]}}


class SpruteLoadDrivingVideo:
    @classmethod
    def INPUT_TYPES(cls):
        files = sorted(str(p.relative_to(folder_paths.get_input_directory()))
                       for p in Path(folder_paths.get_input_directory()).rglob("*.webp"))
        return {"required": {"image": (files, {"image_upload": True})}}

    RETURN_TYPES = ("IMAGE", "MASK", "INT", "BOOLEAN", "FLOAT")
    RETURN_NAMES = ("image", "mask", "loop_frames", "loop", "fps")
    FUNCTION = "load"
    CATEGORY = "Sprute"

    def load(self, image):
        import json
        import math
        from bisect import bisect_right
        import numpy as np
        from PIL import Image
        path = Path(folder_paths.get_annotated_filepath(image))
        frames, starts, elapsed = [], [], 0
        with Image.open(path) as source:
            # Written by Sprute Save Driving Video; other WebPs play once at 24 fps.
            try:
                timing = json.loads(source.getexif().get(0x010E, "{}")).get("sprute_motion_timing")
            except (ValueError, AttributeError):
                timing = None
            if not isinstance(timing, dict) or timing.get("version") != 1:
                timing = {"loop": False, "render_fps": 24}
            interval = int(1000 / timing["render_fps"])
            for i in range(source.n_frames):
                source.seek(i)
                source.load()
                starts.append(elapsed)
                frames.append(torch.from_numpy(np.array(source.convert("RGBA"), dtype=np.float32) / 255))
                elapsed += source.info.get("duration", 0) or interval
        count = max(81, 4 * math.ceil((math.ceil(elapsed / interval) - 1) / 4) + 1)
        loop = timing.get("loop") is True
        selected = []
        for i in range(count):
            at = i * interval % elapsed if loop else min(i * interval, elapsed - 1)
            selected.append(frames[bisect_right(starts, at) - 1])
        batch = torch.stack(selected)
        return batch[..., :3], 1.0 - batch[..., 3], (timing.get("cycle_frames") or 0) if loop else 0, loop, timing["render_fps"]

    @classmethod
    def IS_CHANGED(cls, image):
        return hashlib.sha256(Path(folder_paths.get_annotated_filepath(image)).read_bytes()).hexdigest()


class SpruteStripToGrid:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "mask": ("MASK", {"tooltip": "Load Image's mask: 1 where the image is transparent."})}}

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "arrange"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Arranges a strip of eight directions (S, SE, E, NE, N, NW, W, SW) as the 3x3 grid SCAIL2 reads: "
                   "NW N NE / W - E / SW S SE. Each direction is centred in a square cell with transparent padding, "
                   "without cropping or stretching. The centre is empty and transparent.")

    def arrange(self, image, mask):
        return (layout.strip_to_grid(image, empty=0.0), layout.strip_to_grid(mask, empty=1.0))


class SpruteGridToCells:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "arrange"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Cuts the 3x3 grid into its eight directions, as one batch: every frame of S, then of SE, E, NE, N, NW, W, SW. "
                   "Use it to work on each direction at its own size, such as removing the background.")

    def arrange(self, image):
        return (layout.grid_to_cells(image),)


class SpruteCellsToStrip:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "arrange"
    CATEGORY = "Sprute"
    DESCRIPTION = "Joins the batch from Sprute Grid To Cells into a strip of eight directions: S, SE, E, NE, N, NW, W, SW."

    def arrange(self, image):
        return (layout.cells_to_strip(image),)


class SpruteHoldFirstFrame:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "mask": ("MASK",),
            "count": ("INT", {"default": 5, "min": 1, "max": 64}),
        }}

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "hold"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Repeats the first frame `count` times in front of the video. With the reference as SCAIL2's previous frames, "
                   "those frames are pinned to the reference, so every direction starts from its own view.")

    def hold(self, image, mask, count):
        return (torch.cat([image[:1].repeat(count, 1, 1, 1), image]), torch.cat([mask[:1].repeat(count, 1, 1), mask]))


class SpruteKimodoToGLB:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "motion": ("KIMODO_MOTION",),
            "sample_index": ("INT", {"default": 0, "min": 0, "max": 15}),
        }}

    RETURN_TYPES = ("FILE_3D_GLB",)
    RETURN_NAMES = ("motion_glb",)
    FUNCTION = "convert"
    CATEGORY = "Sprute"

    def convert(self, motion, sample_index=0):
        from io import BytesIO
        from comfy_api.latest import Types
        return (Types.File3D(BytesIO(kimodo.to_glb(motion, sample_index)), file_format="glb"),)


NODE_CLASS_MAPPINGS = {
    "SpruteLoadDrivingVideo": SpruteLoadDrivingVideo,
    "SpruteSaveDrivingVideo": SpruteSaveDrivingVideo,
    "SpruteKimodoToGLB": SpruteKimodoToGLB,
    "SpruteLoadMotion": SpruteLoadMotion,
    "SpruteRenderDrivingVideo": SpruteRenderDrivingVideo,
    "SpruteStripToGrid": SpruteStripToGrid,
    "SpruteGridToCells": SpruteGridToCells,
    "SpruteCellsToStrip": SpruteCellsToStrip,
    "SpruteHoldFirstFrame": SpruteHoldFirstFrame,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SpruteKimodoToGLB": "Sprute Kimodo to GLB",
    "SpruteLoadMotion": "Sprute Load Motion",
    "SpruteRenderDrivingVideo": "Sprute Render Driving Video",
    "SpruteStripToGrid": "Sprute Strip To Grid",
    "SpruteGridToCells": "Sprute Grid To Cells",
    "SpruteCellsToStrip": "Sprute Cells To Strip",
    "SpruteHoldFirstFrame": "Sprute Hold First Frame",
}
