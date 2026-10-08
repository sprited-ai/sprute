"""Sprute nodes for ComfyUI: render a motion on Template-kun into a driving video, and arrange the eight directions."""
import hashlib
from pathlib import Path

import comfy.model_management
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
            "frames": ("INT", {"default": 81, "min": 1, "max": 1000, "tooltip": "SCAIL2 needs 4n+1 frames, such as 81."}),
            "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 1.0}),
            "cell_width": ("INT", {"default": 256, "min": 32, "max": 1024, "step": 32}),
            "cell_height": ("INT", {"default": 256, "min": 32, "max": 1024, "step": 32}),
        }}

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "render"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Renders Template-kun performing the motion in eight directions, as a strip like a sprute animation. "
                   "IMAGE and MASK match what Load Image gives for a transparent driving video.")

    def render(self, motion, frames, fps, cell_width, cell_height):
        device = comfy.model_management.get_torch_device()
        key = (str(device), MODEL.stat().st_mtime_ns)
        if getattr(self, "_key", None) != key:
            self._model, self._key = renderer.Model(MODEL, device), key
        video = renderer.render(self._model, motion, frames, fps, cell_width, cell_height).cpu()
        return (video[..., :3], 1.0 - video[..., 3])


class SpruteStripToGrid:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "mask": ("MASK", {"tooltip": "Load Image's mask: 1 where the image is transparent."})}}

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "arrange"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Arranges a strip of eight directions (S, SE, E, NE, N, NW, W, SW) as the 3x3 grid SCAIL2 reads: "
                   "NW N NE / W - E / SW S SE. The centre is empty and transparent.")

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
    "SpruteKimodoToGLB": SpruteKimodoToGLB,
    "SpruteLoadMotion": SpruteLoadMotion,
    "SpruteRenderDrivingVideo": SpruteRenderDrivingVideo,
    "SpruteStripToGrid": SpruteStripToGrid,
    "SpruteGridToCells": SpruteGridToCells,
    "SpruteCellsToStrip": SpruteCellsToStrip,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SpruteKimodoToGLB": "Sprute Kimodo to GLB",
    "SpruteLoadMotion": "Sprute Load Motion",
    "SpruteRenderDrivingVideo": "Sprute Render Driving Video",
    "SpruteStripToGrid": "Sprute Strip To Grid",
    "SpruteGridToCells": "Sprute Grid To Cells",
    "SpruteCellsToStrip": "Sprute Cells To Strip",
}
