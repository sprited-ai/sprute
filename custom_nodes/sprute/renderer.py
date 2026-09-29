"""Render a motion on Template-kun into an eight-direction driving video. No Blender, no OpenGL.

Skins the mesh in PyTorch and draws it with ComfyUI's PyTorch rasterizer.
"""
import io, math
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from scipy.spatial.transform import Rotation, Slerp
from comfy_extras.sam3d_body.rasterizer import _rasterize_person
from . import layout, motion_file

SUPERSAMPLE = 3
# One camera for every motion, so a seated or crouched body keeps its true size.
# The body is framed for a cell 256 pixels tall; other heights scale with it.
PIXELS_PER_METRE, CENTRE_HEIGHT, ELEVATION = 212.0 / 256, 0.475, math.radians(15)
DISTANCE = 1.0e4        # far enough that the projection is orthographic
KEY_LIGHT, FILL_LIGHT = (-0.45, -0.65, -0.62), (0.6, -0.2, -0.75)
BODY_GRAY = (0.80, 0.80, 0.82)
COMPONENT = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class Model:
    def __init__(self, path: Path, device):
        doc, binary = motion_file.load(path)

        def accessor(index):
            a = doc["accessors"][index]; view = doc["bufferViews"][a["bufferView"]]
            dtype = np.dtype(COMPONENT[a["componentType"]]); width = WIDTH[a["type"]]
            return np.ndarray((a["count"], width), dtype=dtype, buffer=binary,
                              offset=view.get("byteOffset", 0) + a.get("byteOffset", 0),
                              strides=(view.get("byteStride", width * dtype.itemsize), dtype.itemsize)).copy()

        node = next(n for n in doc["nodes"] if "mesh" in n and "skin" in n)
        primitive, = doc["meshes"][node["mesh"]]["primitives"]
        skin = doc["skins"][node["skin"]]
        attributes = primitive["attributes"]
        tensor = lambda a, dtype=torch.float32: torch.as_tensor(np.ascontiguousarray(a), device=device, dtype=dtype)
        self.positions = tensor(accessor(attributes["POSITION"]))
        self.normals = tensor(accessor(attributes["NORMAL"]))
        self.uv = tensor(accessor(attributes["TEXCOORD_0"]))
        self.joints = tensor(accessor(attributes["JOINTS_0"]).astype(np.int64), torch.long)
        self.weights = tensor(accessor(attributes["WEIGHTS_0"]))
        self.faces = tensor(accessor(primitive["indices"]).reshape(-1, 3).astype(np.int64), torch.long)

        nodes = doc["nodes"]
        self.parents = np.full(len(nodes), -1)
        for index, n in enumerate(nodes):
            for child in n.get("children", []):
                self.parents[child] = index
        self.local = np.stack([self._local(n) for n in nodes])
        self.scale = np.array([n.get("scale", [1, 1, 1]) for n in nodes], float)
        self.order = []
        def visit(index):
            self.order.append(index)
            for child in nodes[index].get("children", []):
                visit(child)
        for root in np.where(self.parents == -1)[0]:
            visit(int(root))
        self.rest = self.world({}, None)
        self.skin_joints = np.array(skin["joints"])
        self.inverse_bind = accessor(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
        self.bone = {nodes[i]["name"].removeprefix("mixamorig:"): i for i in self.skin_joints}
        self.hips = self.bone["Hips"]

        material = doc["materials"][primitive["material"]]["pbrMetallicRoughness"]
        image = doc["images"][doc["textures"][material["baseColorTexture"]["index"]]["source"]]
        if "uri" in image:
            source = path.parent / image["uri"]
        else:
            view = doc["bufferViews"][image["bufferView"]]
            start = view.get("byteOffset", 0)
            source = io.BytesIO(binary[start:start + view["byteLength"]])
        pixels = np.asarray(Image.open(source).convert("RGB")).copy()
        self.texture = tensor(pixels).permute(2, 0, 1)[None] / 255

    @staticmethod
    def _local(node):
        if "matrix" in node:
            return np.array(node["matrix"], float).reshape(4, 4).T
        matrix = np.eye(4)
        matrix[:3, :3] = Rotation.from_quat(node.get("rotation", [0, 0, 0, 1])).as_matrix() @ np.diag(node.get("scale", [1, 1, 1]))
        matrix[:3, 3] = node.get("translation", [0, 0, 0])
        return matrix

    def world(self, rotations: dict, hips_position):
        """World matrix of every node, with the given local rotations (3x3) and the hips' local position."""
        world = np.empty_like(self.local)
        for index in self.order:
            local = self.local[index].copy()
            if index in rotations:
                local[:3, :3] = rotations[index] @ np.diag(self.scale[index])
            if hips_position is not None and index == self.hips:
                local[:3, 3] = hips_position
            parent = self.parents[index]
            world[index] = local if parent < 0 else world[parent] @ local
        return world

    def skinned(self, world):
        matrices = torch.as_tensor(world[self.skin_joints] @ self.inverse_bind, device=self.positions.device, dtype=torch.float32)
        blend = (matrices[self.joints] * self.weights[..., None, None]).sum(1)
        positions = torch.einsum("vij,vj->vi", blend[:, :3, :3], self.positions) + blend[:, :3, 3]
        return positions, F.normalize(torch.einsum("vij,vj->vi", blend[:, :3, :3], self.normals), dim=-1)


def camera(direction: int, device):
    """Rotation from model space (Y up, facing +Z) to image space (+X right, +Y down, +Z away)."""
    yaw = math.radians(45 * direction)
    to_z_up = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)
    turn = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])
    sin, cos = math.sin(ELEVATION), math.cos(ELEVATION)
    look_down = np.array([[1, 0, 0], [0, -sin, -cos], [0, cos, -sin]])     # camera above, looking down
    return torch.as_tensor(look_down @ turn @ to_z_up, device=device, dtype=torch.float32)


def render_cell(model: Model, positions, normals, direction: int, cell_width: int, cell_height: int):
    device = positions.device
    width, height = cell_width * SUPERSAMPLE, cell_height * SUPERSAMPLE
    rotation = camera(direction, device)
    centre = torch.tensor([0.0, CENTRE_HEIGHT, 0.0], device=device)
    view = (positions - centre) @ rotation.T
    view[:, 2] += DISTANCE
    view_normals = normals @ rotation.T
    key = F.normalize(torch.tensor(KEY_LIGHT, device=device), dim=0)
    fill = F.normalize(torch.tensor(FILL_LIGHT, device=device), dim=0)
    gray = torch.tensor(BODY_GRAY, device=device)

    def shade(face_index, barycentric):
        corners = model.faces[face_index]
        normal = F.normalize((view_normals[corners] * barycentric[..., None]).sum(1), dim=-1)
        uv = (model.uv[corners] * barycentric[..., None]).sum(1)
        colour = F.grid_sample(model.texture, (uv * 2 - 1)[None, None], mode="bilinear", align_corners=False)[0, :, 0].T
        # Keep the painted face; flatten the body to one gray.
        body = ((colour.mean(1, keepdim=True) - 0.35) / 0.25).clamp(0, 1)
        body = body * body * (3 - 2 * body)
        colour = colour * (1 - body) + gray * body
        light = 0.38 + 0.62 * (normal @ key).clamp(min=0)[:, None] + 0.18 * (normal @ fill).clamp(min=0)[:, None]
        rim = (1 - (-normal[:, 2]).clamp(0, 1)).pow(3)[:, None]
        return (colour * light + 0.10 * rim).clamp(0, 1)

    depth = torch.full((width * height,), float("inf"), device=device)
    colour = torch.zeros((width * height, 3), device=device)
    mask = torch.zeros(width * height, dtype=torch.bool, device=device)
    _rasterize_person(view, model.faces, PIXELS_PER_METRE * height * DISTANCE, width, height, depth, colour, mask, shade)
    alpha = mask.float().view(1, 1, height, width)
    colour = colour.view(height, width, 3).permute(2, 0, 1)[None] * alpha
    alpha, colour = F.avg_pool2d(alpha, SUPERSAMPLE), F.avg_pool2d(colour, SUPERSAMPLE)
    return torch.cat([(colour / alpha.clamp(min=1e-6))[0], alpha[0]], 0).permute(1, 2, 0).clamp(0, 1)


def sample_motion(model: Model, motion, frames: int, frame_rate: float):
    """Local bone rotations and hips positions for `frames` frames at `frame_rate`."""
    name, fps, loop, rotations, hips = motion
    count = len(hips)
    position = np.arange(frames) / frame_rate * fps
    close = lambda values: np.concatenate([values, values[:1]]) if loop else values     # frame `count` is frame 0 again
    if loop:
        position = position % count
    else:
        position = np.minimum(position, count - 1)        # a clip that ends early holds its last pose
    keys = np.arange(count + (1 if loop else 0))
    bones = [model.bone[bone] for bone in rotations]
    turned = np.stack([Slerp(keys, Rotation.from_quat(close(values)))(position).as_matrix() for values in rotations.values()], 1)
    moved = np.stack([np.interp(position, keys, close(hips)[:, axis]) for axis in range(3)], 1)
    return [(dict(zip(bones, turned[f])), moved[f]) for f in range(frames)]


def render(model: Model, motion, frames: int = 81, frame_rate: float = 24, cell_width: int = 192, cell_height: int = 256):
    """(frames, cell_height, 8 * cell_width, 4) RGBA in 0..1: the eight directions in a strip, like a sprute animation."""
    device = model.positions.device
    video = torch.zeros((frames, cell_height, cell_width * len(layout.STRIP), 4), device=device)
    for frame, (rotations, hips) in enumerate(sample_motion(model, motion, frames, frame_rate)):
        positions, normals = model.skinned(model.world(rotations, hips))
        for direction in range(len(layout.STRIP)):
            left = direction * cell_width
            video[frame, :, left:left + cell_width] = render_cell(model, positions, normals, direction, cell_width, cell_height)
    return video
