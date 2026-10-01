"""Read and write sprute motion files: a GLB holding Template-kun's skeleton and one animation, no mesh.

The animation stores each animated bone's local rotation per frame, and the hips' position.
"""
import json, struct
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

COMPONENT = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load(path: Path):
    """The glTF document and its binary buffer, from a .glb or a .gltf."""
    if path.suffix == ".glb":
        raw = path.read_bytes()
        size = struct.unpack_from("<I", raw, 12)[0]
        start = 20 + size
        return json.loads(raw[20:start]), raw[start + 8:start + 8 + struct.unpack_from("<I", raw, start)[0]]
    doc = json.loads(path.read_text())
    return doc, (path.parent / doc["buffers"][0]["uri"]).read_bytes()


def accessor(doc, binary, index):
    a = doc["accessors"][index]; view = doc["bufferViews"][a["bufferView"]]
    dtype = np.dtype(COMPONENT[a["componentType"]]); width = WIDTH[a["type"]]
    return np.ndarray((a["count"], width), dtype=dtype, buffer=binary,
                      offset=view.get("byteOffset", 0) + a.get("byteOffset", 0),
                      strides=(view.get("byteStride", width * dtype.itemsize), dtype.itemsize)).copy()


def write(path: Path, model_path: Path, name: str, fps: float, loop: bool, rotations: dict, hips_translation, source: str = ""):
    """rotations: bone node index -> (frames, 4) local quaternions. hips_translation: (frames, 3) local position."""
    model, model_binary = load(model_path)
    skin = model["skins"][0]
    hips = next(i for i in skin["joints"] if model["nodes"][i]["name"].endswith("Hips"))
    frames = len(hips_translation)
    close = lambda values: np.concatenate([values, values[:1]]) if loop else values      # a loop ends on its first frame
    times = np.arange(frames + (1 if loop else 0), dtype=np.float32) / fps

    blob, views, accessors = bytearray(), [], []
    def add(values, kind, bounds=False):
        values = np.ascontiguousarray(values, dtype=np.float32)
        blob.extend(b"\0" * (-len(blob) % 4))
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": values.nbytes})
        blob.extend(values.tobytes())
        entry = {"bufferView": len(views) - 1, "componentType": 5126, "count": len(values), "type": kind}
        if bounds:
            entry["min"], entry["max"] = [float(values.min())], [float(values.max())]
        accessors.append(entry)
        return len(accessors) - 1

    time = add(times, "SCALAR", bounds=True)
    samplers, channels = [], []
    def channel(node, target, values, kind):
        samplers.append({"input": time, "output": add(close(values), kind), "interpolation": "LINEAR"})
        channels.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": target}})
    channel(hips, "translation", hips_translation, "VEC3")
    for node, values in rotations.items():
        channel(node, "rotation", values, "VEC4")
    bind = add(accessor(model, model_binary, skin["inverseBindMatrices"]).reshape(-1, 16), "MAT4")

    nodes = [{key: value for key, value in node.items() if key not in ("mesh", "skin")} for node in model["nodes"]]
    doc = {"asset": {"version": "2.0", "generator": "sprute"}, "scene": 0, "scenes": model["scenes"], "nodes": nodes,
           "skins": [{"joints": skin["joints"], "inverseBindMatrices": bind}],
           "animations": [{"name": name, "samplers": samplers, "channels": channels,
                           "extras": {"fps": fps, "loop": loop, "frames": frames, "source": source}}],
           "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    text = json.dumps(doc, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    blob.extend(b"\0" * (-len(blob) % 4))
    body = struct.pack("<II", len(text), 0x4E4F534A) + text + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)


def read(path: Path):
    """name, fps, loop, {bone name: (frames, 4) local quaternions}, (frames, 3) hips position."""
    doc, binary = load(path)
    animation, = doc["animations"]
    extras = animation["extras"]
    rotations, hips = {}, None
    for entry in animation["channels"]:
        values = accessor(doc, binary, animation["samplers"][entry["sampler"]]["output"]).astype(float)[:extras["frames"]]
        bone = doc["nodes"][entry["target"]["node"]]["name"].removeprefix("mixamorig:")
        if entry["target"]["path"] == "rotation":
            rotations[bone] = values
        else:
            hips = values
    return animation["name"], float(extras["fps"]), bool(extras["loop"]), rotations, hips


def local_motion(pose, parents, hips, rotations: list, offsets):
    """Turn world-space turns away from the T-pose into local rotations on Template-kun's skeleton.

    pose(turns, offset) -> world matrices. rotations: per frame, {node index: 3x3 world turn}.
    offsets: (frames, 3) hips offsets from the rest position, in metres.
    """
    nodes = sorted(rotations[0])
    local = {node: [] for node in nodes}
    moved = []
    for turned, offset in zip(rotations, offsets):
        world = pose(turned, offset)
        relative = lambda node: world[node] if parents[node] < 0 else np.linalg.inv(world[parents[node]]) @ world[node]
        for node in nodes:
            matrix = relative(node)[:3, :3]
            local[node].append(Rotation.from_matrix(matrix / np.linalg.norm(matrix, axis=0)).as_quat())
        moved.append(relative(hips)[:3, 3])
    return {node: np.array(values) for node, values in local.items()}, np.array(moved)
