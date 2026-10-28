"""Sprute nodes for ComfyUI: render a motion on Template-kun into a driving video, and arrange the eight directions."""
import hashlib
from pathlib import Path

import comfy.model_management
import torch
import folder_paths

import json
import uuid

from . import check, kimodo, layout, motion_file, renderer, retarget, snap

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
            "snap_to_multiple": ("INT", {"default": 2, "min": 0, "max": 100,
                                         "tooltip": "Fit the motion's length to a multiple of this many frames, the N of Select Every Nth, "
                                                    "so a loop wraps cleanly and a clip ends on its last pose. "
                                                    "The motion plays slightly faster or slower at fps. 0 keeps its exact speed."}),
        }}

    RETURN_TYPES = ("IMAGE", "MASK", "FLOAT", "INT")
    RETURN_NAMES = ("IMAGE", "MASK", "time_scale", "keep_frames")
    OUTPUT_TOOLTIPS = ("", "", "How many times as long the motion plays at fps after snapping; 1.0 when snap_to_multiple is 0.",
                       "Frames to keep once snapped: one cycle of a loop, so it wraps cleanly, or a clip up to its last pose. "
                       "All frames otherwise.")
    FUNCTION = "render"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Renders Template-kun performing the motion in eight directions, as a strip like a sprute animation. "
                   "IMAGE and MASK match what Load Image gives for a transparent driving video.")

    def render(self, motion, frames, fps, cell_width, cell_height, snap_to_multiple):
        device = comfy.model_management.get_torch_device()
        key = (str(device), MODEL.stat().st_mtime_ns)
        if getattr(self, "_key", None) != key:
            self._model, self._key = renderer.Model(MODEL, device), key
        scale = snap.time_scale(motion, fps, snap_to_multiple)
        video = renderer.render(self._model, motion, frames, fps * scale, cell_width, cell_height).cpu()
        return (video[..., :3], 1.0 - video[..., 3], scale, snap.keep_frames(motion, fps, snap_to_multiple, frames))


class SpruteRenderRigVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "rig": (sorted(str(path.relative_to(Path(folder_paths.get_input_directory())))
                           for path in Path(folder_paths.get_input_directory()).rglob("*.glb")),
                    {"tooltip": "A skinned, animated GLB in ComfyUI's input folder, such as a four-legged animal."}),
            "animation": ("STRING", {"default": "", "tooltip": "Which of the rig's own animations, by name. Empty picks the first."}),
            "body": (["auto", "own"], {"tooltip": "auto: Template-kun performs a humanoid rig's animation and any other rig plays on "
                                                 "itself. own: the rig always plays on itself, humanoid or not."}),
            "loop": ("BOOLEAN", {"default": True}),
            "size": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 3.0, "step": 0.05,
                               "tooltip": "The rig's longest side in metres; Template-kun stands about 1.1 m tall."}),
            "frames": ("INT", {"default": 81, "min": 1, "max": 1000, "tooltip": "SCAIL2 needs 4n+1 frames, such as 81."}),
            "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 1.0}),
            "cell_width": ("INT", {"default": 256, "min": 32, "max": 1024, "step": 32}),
            "cell_height": ("INT", {"default": 256, "min": 32, "max": 1024, "step": 32}),
            "snap_to_multiple": ("INT", {"default": 2, "min": 0, "max": 100}),
        }}

    RETURN_TYPES = ("IMAGE", "MASK", "FLOAT", "INT")
    RETURN_NAMES = ("IMAGE", "MASK", "time_scale", "keep_frames")
    FUNCTION = "render"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Renders a skinned GLB's animation in eight directions, like Render Driving Video. A humanoid rig's animation is "
                   "retargeted onto Template-kun unless body is own; any other rig, such as a four-legged animal, plays on itself.")

    def render(self, rig, animation, body, loop, size, frames, fps, cell_width, cell_height, snap_to_multiple):
        path = Path(folder_paths.get_annotated_filepath(rig))
        device = comfy.model_management.get_torch_device()
        if body == "auto" and retarget.humanoid(path):
            model, motion = renderer.Model(MODEL, device), retarget.retarget(path, animation.strip(), MODEL)
        else:
            model, motion = renderer.Model(path, device), motion_file.own(path, animation.strip(), loop)
            model.fit(size)
        scale = snap.time_scale(motion, fps, snap_to_multiple)
        video = renderer.render(model, motion, frames, fps * scale, cell_width, cell_height).cpu()
        return (video[..., :3], 1.0 - video[..., 3], scale, snap.keep_frames(motion, fps, snap_to_multiple, frames))


class SpruteStripToGrid:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "mask": ("MASK", {"tooltip": "Load Image's mask: 1 where the image is transparent."})},
                "optional": {"directions": (["8", "4"], {"default": "8", "tooltip": "4 keeps only the diagonals: SE, NE, NW, SW."})}}

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "arrange"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Arranges a strip of eight directions (S, SE, E, NE, N, NW, W, SW) as the 3x3 grid SCAIL2 reads: "
                   "NW N NE / W - E / SW S SE. Each direction is centred in a square cell with transparent padding, "
                   "without cropping or stretching. The centre is empty and transparent. "
                   "With 4 directions, only the diagonals, as a 2x2 grid: NW NE / SW SE.")

    def arrange(self, image, mask, directions="8"):
        return (layout.strip_to_grid(image, empty=0.0, directions=int(directions)),
                layout.strip_to_grid(mask, empty=1.0, directions=int(directions)))


class SpruteGridToCells:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}, "optional": {"directions": (["8", "4"], {"default": "8", "tooltip": "4 keeps only the diagonals: SE, NE, NW, SW."})}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "arrange"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Cuts the 3x3 grid into its eight directions, as one batch: every frame of S, then of SE, E, NE, N, NW, W, SW. "
                   "Use it to work on each direction at its own size, such as removing the background. "
                   "With 4 directions, the 2x2 grid's SE, NE, NW, SW.")

    def arrange(self, image, directions="8"):
        return (layout.grid_to_cells(image, directions=int(directions)),)


class SpruteCellsToStrip:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}, "optional": {"directions": (["8", "4"], {"default": "8", "tooltip": "4 keeps only the diagonals: SE, NE, NW, SW."})}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "arrange"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Joins the batch from Sprute Grid To Cells into a strip of eight directions: S, SE, E, NE, N, NW, W, SW. "
                   "With 4 directions, S, E, N and W are left transparent.")

    def arrange(self, image, directions="8"):
        return (layout.cells_to_strip(image, directions=int(directions)),)


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


class SpruteCheckDirections:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "animation": ("IMAGE", {"tooltip": "An animation strip, as Load Image gives a sprute animation."}),
            "animation_mask": ("MASK",),
            "reference": ("IMAGE", {"tooltip": "The character's directions strip."}),
            "reference_mask": ("MASK",),
            "clip_vision": ("CLIP_VISION",),
        }, "optional": {"directions": (["8", "4"], {"default": "8", "tooltip": "4 checks only the diagonals: SE, NE, NW, SW."})}}

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "check"
    CATEGORY = "Sprute"
    DESCRIPTION = ("Measures each direction of an animation against the character's own view of that direction: identity, "
                   "facing, coverage and colour per frame, and a pass or fail per direction. Saves them as JSON.")

    def check(self, animation, animation_mask, reference, reference_mask, clip_vision, directions="8"):
        def embed(images):
            return torch.cat([clip_vision.encode_image(images[i:i + 32], crop=False)["image_embeds"].float()
                              for i in range(0, images.shape[0], 32)])
        measurements = check.measure(animation, 1.0 - animation_mask, reference, 1.0 - reference_mask, embed,
                                     directions=int(directions))
        report = {"directions": measurements, "verdict": check.verdict(measurements)}
        name = f"check_{uuid.uuid4().hex}.json"
        folder = Path(folder_paths.get_output_directory())
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(json.dumps(report))
        return {"ui": {"images": [{"filename": name, "subfolder": "", "type": "output"}]}}


NODE_CLASS_MAPPINGS = {
    "SpruteKimodoToGLB": SpruteKimodoToGLB,
    "SpruteLoadMotion": SpruteLoadMotion,
    "SpruteRenderDrivingVideo": SpruteRenderDrivingVideo,
    "SpruteRenderRigVideo": SpruteRenderRigVideo,
    "SpruteStripToGrid": SpruteStripToGrid,
    "SpruteGridToCells": SpruteGridToCells,
    "SpruteCellsToStrip": SpruteCellsToStrip,
    "SpruteHoldFirstFrame": SpruteHoldFirstFrame,
    "SpruteCheckDirections": SpruteCheckDirections,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SpruteKimodoToGLB": "Sprute Kimodo to GLB",
    "SpruteLoadMotion": "Sprute Load Motion",
    "SpruteRenderDrivingVideo": "Sprute Render Driving Video",
    "SpruteRenderRigVideo": "Sprute Render Rig Video",
    "SpruteStripToGrid": "Sprute Strip To Grid",
    "SpruteGridToCells": "Sprute Grid To Cells",
    "SpruteCellsToStrip": "Sprute Cells To Strip",
    "SpruteHoldFirstFrame": "Sprute Hold First Frame",
    "SpruteCheckDirections": "Sprute Check Directions",
}
