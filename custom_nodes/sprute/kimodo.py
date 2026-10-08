"""Export Kimodo's original motion; retarget only when loading it for rendering."""
import json
import struct
import numpy as np
from scipy.spatial.transform import Rotation
from . import motion_file, retarget

MAPPING = {"Hips": "Hips", "Spine1": "Spine", "Spine2": "Spine1",
           "Chest": "Spine2", "Neck1": "Neck", "Head": "Head"}
for side in ("Left", "Right"):
    MAPPING.update({side + a: side + b for a, b in (
        ("Shoulder", "Shoulder"), ("Arm", "Arm"), ("ForeArm", "ForeArm"),
        ("Hand", "Hand"), ("Leg", "UpLeg"), ("Shin", "Leg"),
        ("Foot", "Foot"), ("ToeBase", "ToeBase"))})


def to_glb(motion, sample_index=0):
    """An animated skeleton with joint metadata, no character mesh or textures."""
    def array(value):
        if hasattr(value, "detach"):
            value = value.detach().cpu().numpy()
        return np.asarray(value)

    positions = array(motion.output_dict["posed_joints"])
    world_rotations = array(motion.output_dict["global_rot_mats"])
    if not 0 <= sample_index < len(positions):
        raise ValueError(f"Kimodo sample {sample_index} is unavailable; got {len(positions)} samples")
    positions, world_rotations = positions[sample_index], world_rotations[sample_index]
    parents = list(motion.joint_parents)
    names = list(motion.joint_names)
    neutral = array(motion.neutral_joints)
    frames, joints, _ = positions.shape
    roots = [i for i, p in enumerate(parents) if p == -1]
    if (len(roots) != 1 or len(parents) != joints or len(names) != joints
            or neutral.shape != (joints, 3) or world_rotations.shape != (frames, joints, 3, 3)
            or any(p < -1 or p >= i for i, p in enumerate(parents))):
        raise ValueError("Expected a Kimodo skeleton with parents ordered before their children")
    fps = float(motion.fps)
    if frames < 1 or not np.isfinite(fps) or fps <= 0 or not all(
        np.isfinite(a).all() for a in (positions, world_rotations, neutral)
    ):
        raise ValueError("Invalid Kimodo motion")

    blob, views, accessors, samplers, channels = bytearray(), [], [], [], []
    def add(values, kind, bounds=False):
        values = np.ascontiguousarray(values, dtype="<f4")
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": values.nbytes})
        blob.extend(values.tobytes())
        item = {"bufferView": len(views) - 1, "componentType": 5126, "count": len(values), "type": kind}
        if bounds:
            item.update(min=[float(values.min())], max=[float(values.max())])
        accessors.append(item)
        return len(accessors) - 1

    time = add(np.arange(frames) / fps, "SCALAR", bounds=True)
    nodes = []
    for joint, parent in enumerate(parents):
        rest = neutral[joint] if parent < 0 else neutral[joint] - neutral[parent]
        node = {"name": names[joint], "translation": rest.tolist()}
        nodes.append(node)
        if parent >= 0:
            nodes[parent].setdefault("children", []).append(joint)
        turns, moved = world_rotations[:, joint], positions[:, joint]
        if parent >= 0:
            inverse = np.swapaxes(world_rotations[:, parent], -1, -2)
            turns = inverse @ turns
            moved = (inverse @ (moved - positions[:, parent])[..., None])[..., 0]
        quaternions = Rotation.from_matrix(turns).as_quat()
        # Keep adjacent keys in the same quaternion hemisphere for interpolation.
        signs = np.where(np.sum(quaternions[1:] * quaternions[:-1], axis=1) < 0, -1, 1)
        quaternions[1:] *= np.cumprod(signs)[:, None]
        for target, values, kind in (("translation", moved, "VEC3"), ("rotation", quaternions, "VEC4")):
            samplers.append({"input": time, "output": add(values, kind), "interpolation": "LINEAR"})
            channels.append({"sampler": len(samplers) - 1, "target": {"node": joint, "path": target}})

    # Viewers identify bones through skins.joints, even without a skinned mesh.
    inverse_bind = np.tile(np.eye(4), (joints, 1, 1))
    inverse_bind[:, :3, 3] = -neutral
    bind = add(inverse_bind.transpose(0, 2, 1).reshape(joints, 16), "MAT4")
    doc = {"asset": {"version": "2.0", "generator": "sprute-kimodo"},
           "scene": 0, "scenes": [{"nodes": roots}], "nodes": nodes,
           "skins": [{"joints": list(range(joints)), "skeleton": roots[0], "inverseBindMatrices": bind}],
           "animations": [{"name": "kimodo", "samplers": samplers, "channels": channels,
                           "extras": {"fps": fps, "frames": frames, "loop": False, "source": "Kimodo",
                                      "model": motion.model_name, "skeleton": motion.skeleton_name}}],
           "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    text = json.dumps(doc, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    body = struct.pack("<II", len(text), 0x4E4F534A) + text + struct.pack("<II", len(blob), 0x004E4942) + blob
    return struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body


def load_motion(path, model_path):
    """Apply a saved SOMA77 clip to Template-kun at the driving-render stage."""
    doc, binary = motion_file.load(path)
    animation, = doc["animations"]
    names = [node["name"] for node in doc["nodes"]]
    frames = animation["extras"]["frames"]
    rotations = np.broadcast_to(np.eye(3), (frames, len(names), 3, 3)).copy()
    parents = [-1] * len(names)
    neutral = np.array([node["translation"] for node in doc["nodes"]])
    for i, node in enumerate(doc["nodes"]):
        for child in node.get("children", []):
            parents[child] = i
    root, = [i for i, parent in enumerate(parents) if parent < 0]
    roots = np.repeat(neutral[root][None], frames, axis=0)
    for channel in animation["channels"]:
        target = channel["target"]
        values = motion_file.accessor(doc, binary, animation["samplers"][channel["sampler"]]["output"])
        if target["path"] == "rotation":
            rotations[:, target["node"]] = Rotation.from_quat(values).as_matrix()
        elif target["node"] == root and target["path"] == "translation":
            roots = values
    for i, parent in enumerate(parents):
        if parent >= 0:
            rotations[:, i] = rotations[:, parent] @ rotations[:, i]
            neutral[i] += neutral[parent]
    if not all(name in names for name in MAPPING):
        raise ValueError("Expected SOMA motion with named joints")
    height = float(neutral[root, 1] - neutral[:, 1].min())
    if not np.isfinite(height) or height <= 0 or not all(
        np.isfinite(values).all() for values in (rotations, roots)
    ):
        raise ValueError("Invalid Kimodo motion")
    target = retarget.Skeleton(model_path)
    scale = target.rest[target.hips, 1, 3] / height
    offsets = np.array(roots, dtype=float, copy=True)
    offsets[:, 1] -= height
    # Retain horizontal travel; the common renderer chooses in-place or moving.
    offsets[:, [0, 2]] -= offsets[0, [0, 2]]
    mapping = [(names.index(src), target.bone[dst]) for src, dst in MAPPING.items()]
    turns = [{dst: frame[src] for src, dst in mapping} for frame in rotations]
    local, moved = motion_file.local_motion(target.pose, target.parents, target.hips, turns, offsets * scale)
    named = {target.doc["nodes"][node]["name"].removeprefix("mixamorig:"): values for node, values in local.items()}
    return animation["name"], float(animation["extras"]["fps"]), False, named, moved
