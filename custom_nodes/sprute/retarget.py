"""Retarget an animation from any humanoid GLB onto Template-kun's skeleton.

Handles a different rest pose (A-pose or T-pose) and different proportions. Bones are matched by name.
"""
import json, struct
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from . import motion_file

FPS = 24
PREFIXES = ("mixamorig:", "mixamorig_", "mixamorig")
BONES = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head"] + [
    side + part for side in ("Left", "Right")
    for part in ("Shoulder", "Arm", "ForeArm", "Hand", "UpLeg", "Leg", "Foot", "ToeBase")]
# The bone whose joint a bone points at. Bones without one borrow their parent's correction.
POINTS_AT = {"Spine": "Spine1", "Spine1": "Spine2", "Spine2": "Neck", "Neck": "Head"}
BORROWS = {"Head": "Neck"}
for side in ("Left", "Right"):
    POINTS_AT.update({f"{side}Shoulder": f"{side}Arm", f"{side}Arm": f"{side}ForeArm", f"{side}ForeArm": f"{side}Hand",
                      f"{side}UpLeg": f"{side}Leg", f"{side}Leg": f"{side}Foot", f"{side}Foot": f"{side}ToeBase"})
    BORROWS.update({f"{side}Hand": f"{side}ForeArm", f"{side}ToeBase": f"{side}Foot"})
COMPONENT = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class Skeleton:
    def __init__(self, path: Path):
        if path.suffix == ".glb":
            raw = path.read_bytes()
            size = struct.unpack_from("<I", raw, 12)[0]
            self.doc = json.loads(raw[20:20 + size])
            start = 20 + size
            self.binary = raw[start + 8:start + 8 + struct.unpack_from("<I", raw, start)[0]]
        else:
            self.doc = json.loads(path.read_text())
            self.binary = (path.parent / self.doc["buffers"][0]["uri"]).read_bytes()
        nodes = self.doc["nodes"]
        self.parents = np.full(len(nodes), -1)
        for index, node in enumerate(nodes):
            for child in node.get("children", []):
                self.parents[child] = index
        self.order = []
        def visit(index):
            self.order.append(index)
            for child in nodes[index].get("children", []):
                visit(child)
        for root in np.where(self.parents == -1)[0]:
            visit(int(root))
        self.translation = np.array([n.get("translation", [0, 0, 0]) for n in nodes], float)
        self.rotation = np.array([n.get("rotation", [0, 0, 0, 1]) for n in nodes], float)
        self.scale = np.array([n.get("scale", [1, 1, 1]) for n in nodes], float)
        self.bone = {}
        for index in self.doc["skins"][0]["joints"]:
            name = nodes[index]["name"]
            for prefix in PREFIXES:
                name = name.removeprefix(prefix)
            self.bone[name] = index
        self.rest = self.world(self.translation, self.rotation)
        self.local = np.stack([self.rest[i] if self.parents[i] < 0 else np.linalg.inv(self.rest[self.parents[i]]) @ self.rest[i]
                               for i in range(len(nodes))])
        self.hips = self.bone["Hips"]

    def accessor(self, index):
        a = self.doc["accessors"][index]; view = self.doc["bufferViews"][a["bufferView"]]
        dtype = np.dtype(COMPONENT[a["componentType"]]); width = WIDTH[a["type"]]
        return np.ndarray((a["count"], width), dtype=dtype, buffer=self.binary,
                          offset=view.get("byteOffset", 0) + a.get("byteOffset", 0),
                          strides=(view.get("byteStride", width * dtype.itemsize), dtype.itemsize)).copy()

    def world(self, translation, rotation):
        world = np.empty((len(self.parents), 4, 4))
        for index in self.order:
            local = np.eye(4)
            local[:3, :3] = Rotation.from_quat(rotation[index]).as_matrix() @ np.diag(self.scale[index])
            local[:3, 3] = translation[index]
            parent = self.parents[index]
            world[index] = local if parent < 0 else world[parent] @ local
        return world

    def pose(self, turns: dict, hips_offset):
        """World matrices with the given bones turned away from the rest pose; other bones follow their parent."""
        world = np.empty_like(self.rest)
        for index in self.order:
            parent = self.parents[index]
            world[index] = self.local[index] if parent < 0 else world[parent] @ self.local[index]
            if index in turns:
                world[index, :3, :3] = turns[index] @ self.rest[index, :3, :3]
            if index == self.hips:
                world[index, :3, 3] = self.rest[index, :3, 3] + hips_offset
        return world

    def animation(self, name):
        """World matrices per frame at FPS, without a duplicated closing frame."""
        available = self.doc.get("animations", [])
        found = [a for a in available if name.lower() in a.get("name", "").lower()] if name else available[:1]
        if len(found) != 1:
            raise ValueError(f"animation {name!r} not found; the file has: {[a.get('name') for a in available]}")
        channels = []
        for channel in found[0]["channels"]:
            sampler = found[0]["samplers"][channel["sampler"]]
            if sampler.get("interpolation", "LINEAR") not in ("LINEAR", "STEP"):
                raise ValueError("cubic spline keyframes are not supported; bake the animation to linear keys")
            channels.append((channel["target"]["node"], channel["target"]["path"], sampler.get("interpolation", "LINEAR"),
                             self.accessor(sampler["input"]).ravel().astype(float), self.accessor(sampler["output"]).astype(float)))
        start = min(c[3][0] for c in channels); end = max(c[3][-1] for c in channels)
        times = start + np.arange(int(round((end - start) * FPS)) + 1) / FPS
        translation = np.repeat(self.translation[None], len(times), 0)
        rotation = np.repeat(self.rotation[None], len(times), 0)
        for node, path, interpolation, keys, values in channels:
            if path == "scale" or len(keys) < 2:
                continue
            at = np.clip(times, keys[0], keys[-1])
            if interpolation == "STEP":
                picked = values[np.searchsorted(keys, at, side="right") - 1]
                (translation if path == "translation" else rotation)[:, node] = picked
            elif path == "translation":
                translation[:, node] = np.stack([np.interp(at, keys, values[:, axis]) for axis in range(3)], 1)
            else:
                rotation[:, node] = Slerp(keys, Rotation.from_quat(values))(at).as_quat()
        frames = np.stack([self.world(translation[f], rotation[f]) for f in range(len(times))])
        step = np.abs(frames[1, :, :3, :3] - frames[0, :, :3, :3]).max()
        closing = np.abs(frames[-1, :, :3, :3] - frames[0, :, :3, :3]).max()
        return frames[:-1] if closing < 0.25 * step else frames


def pure(matrix):
    """Rotation part without scale."""
    return Rotation.from_matrix(matrix[..., :3, :3] / np.linalg.norm(matrix[..., :3, :3], axis=-2, keepdims=True)).as_matrix()


def shortest_turn(a, b):
    """Rotation that takes direction a to direction b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    axis = np.cross(a, b); sine = np.linalg.norm(axis)
    if sine < 1e-8:
        return np.eye(3)
    return Rotation.from_rotvec(axis / sine * np.arctan2(sine, a @ b)).as_matrix()


def rest_corrections(source: Skeleton, target: Skeleton, align: bool):
    correction = {}
    for name in BONES:
        if not align or name not in POINTS_AT:
            continue
        direction = lambda s: s.rest[s.bone[POINTS_AT[name]], :3, 3] - s.rest[s.bone[name], :3, 3]
        correction[name] = shortest_turn(direction(source), direction(target))
    for name, other in BORROWS.items():
        if other in correction:
            correction[name] = correction[other]
    return correction


def retarget(source_path: Path, animation: str, model_path: Path):
    """name, fps, loop, {bone name: (frames, 4) local quaternions}, (frames, 3) hips positions, on Template-kun."""
    source, target = Skeleton(source_path), Skeleton(model_path)
    missing = [name for name in BONES if name not in source.bone]
    if missing:
        raise ValueError(f"{source_path.name}: no bones named {', '.join(missing)}. Bones are matched by Mixamo names.")
    facing = lambda s: s.rest[s.bone["LeftUpLeg"], 0, 3] - s.rest[s.bone["RightUpLeg"], 0, 3]
    if facing(source) * facing(target) <= 0:
        raise ValueError(f"{source_path.name}: the character faces away from +Z")
    correction = rest_corrections(source, target, True)
    frames = source.animation(animation)
    rest = pure(np.stack([source.rest[source.bone[name]] for name in BONES]))
    posed = pure(np.stack([frames[:, source.bone[name]] for name in BONES], 1))
    turn = posed @ np.swapaxes(rest, -1, -2)
    for index, name in enumerate(BONES):
        if name in correction:
            turn[:, index] = turn[:, index] @ correction[name].T
    ground = min(source.rest[i, 1, 3] for i in source.bone.values())
    offset = frames[:, source.hips, :3, 3] - source.rest[source.hips, :3, 3]
    # Driving videos play in place: drop where the clip stands, keep the sway and the vertical movement.
    offset[:, [0, 2]] -= offset[:, [0, 2]].mean(0)
    scale = target.rest[target.hips, 1, 3] / (source.rest[source.hips, 1, 3] - ground)
    turns = [{target.bone[name]: turn[f, index] for index, name in enumerate(BONES)} for f in range(len(turn))]
    rotations, moved = motion_file.local_motion(target.pose, target.parents, target.hips, turns, offset * scale)
    names = {index: name for name, index in target.bone.items()}
    return animation, float(FPS), True, {names[node]: values for node, values in rotations.items()}, moved
