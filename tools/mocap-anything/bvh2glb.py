"""Append a MoCapAnything BVH to a rig GLB as a new clip.

python bvh2glb.py RIG.glb PRED.bvh OUT.glb CLIP [--start F --end F] [--fps N]

The BVH is on the rig's own skeleton (same joint names), but in MoCapAnything's frame: +Z facing,
different units, its own bone rolls. Each bone gets the BVH joint's world-space rotation change from
its rest pose, carried into the GLB's frame by the rotation that best maps the GLB rest joints onto the
BVH rest joints (Kabsch). The root also gets the BVH root's translation change, rescaled. Every other
part of the GLB is left as it is.
"""
import argparse, json, struct
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R


def read_glb(path):
    raw = Path(path).read_bytes()
    size = struct.unpack_from("<I", raw, 12)[0]
    doc = json.loads(raw[20:20 + size])
    blen = struct.unpack_from("<I", raw, 20 + size)[0]
    return doc, bytearray(raw[28 + size:28 + size + blen])


def write_glb(path, doc, binary):
    while len(binary) % 4: binary += b"\0"
    doc["buffers"][0]["byteLength"] = len(binary)
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    out = struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(binary))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(binary), 0x004E4942) + binary
    Path(path).write_bytes(out)


def read_bvh(path):
    """Joint names, parents, offsets, and per-frame (root position, world rotations)."""
    names, parents, offsets, channels = [], [], [], []
    stack, lines = [], Path(path).read_text().split("\n")
    i = 0
    while not lines[i].strip().startswith("MOTION"):
        t = lines[i].split()
        if t and t[0] in ("ROOT", "JOINT"):
            names.append(t[1]); parents.append(stack[-1] if stack else -1)
        elif t and t[0] == "End":
            names.append(None); parents.append(stack[-1])
        elif t and t[0] == "{":
            stack.append(len(names) - 1)
        elif t and t[0] == "}":
            stack.pop()
        elif t and t[0] == "OFFSET":
            offsets.append([float(x) for x in t[1:4]])
        elif t and t[0] == "CHANNELS":
            channels.append((len(names) - 1, t[2:]))
        i += 1
    frame_time = float(lines[i + 2].split()[-1])
    data = np.array([[float(x) for x in l.split()] for l in lines[i + 3:] if l.strip()])
    n = len(names)
    local = np.tile(R.identity().as_quat(), (len(data), n, 1))
    root_pos = np.zeros((len(data), 3))
    col = 0
    for j, ch in channels:
        pos = [c for c in ch if c.endswith("position")]
        rot = [c[0] for c in ch if c.endswith("rotation")]
        if pos:
            root_pos = data[:, col:col + 3]
        col += len(pos)
        local[:, j] = R.from_euler("".join(rot), data[:, col:col + 3], degrees=True).as_quat()
        col += len(rot)
    world = np.empty_like(local)
    for j in range(n):
        world[:, j] = local[:, j] if parents[j] < 0 else (R.from_quat(world[:, parents[j]]) * R.from_quat(local[:, j])).as_quat()
    offsets = np.array(offsets)
    rest_pos = np.zeros((n, 3))
    pos = np.zeros((len(data), n, 3))
    for j in range(n):
        p = parents[j]
        rest_pos[j] = offsets[j] + (rest_pos[p] if p >= 0 else 0)
        pos[:, j] = root_pos if p < 0 else pos[:, p] + R.from_quat(world[:, p]).apply(offsets[j])
    return names, parents, rest_pos, pos, world, round(1 / frame_time)


def node_trs(node):
    return (np.array(node.get("translation", [0, 0, 0]), float), R.from_quat(node.get("rotation", [0, 0, 0, 1])),
            np.array(node.get("scale", [1, 1, 1]), float))


def kabsch(a, b):
    """Rotation r minimising |r(a) - b| for centred point sets."""
    a, b = a - a.mean(0), b - b.mean(0)
    a /= np.linalg.norm(a); b /= np.linalg.norm(b)
    return R.align_vectors(b, a)[0]


TORSO = ["Body", "Back", "Torso", "Torso2", "Torso3", "Neck1",
         "FrontShoulder.L", "FrontShoulder.R", "BackShoulder.L", "BackShoulder.R"]


def orient_from_pose(names, bpos, bworld, pose, ref, window=5):
    """Turn each frame's whole body so its torso faces as in the predicted joint positions.

    MoCapAnything's rotation output keeps the body level (a leap's rear-up and nose-down landing are
    lost); its position output has them. Per frame, the rotation taking the BVH torso onto the
    predicted torso, relative to the same rotation at frame `ref`, is applied to every joint."""
    order = [n for n in names if n]  # pose_pred.npy joints follow the BVH's JOINT order
    bi = [names.index(n) for n in TORSO]
    pi = [order.index(n) for n in TORSO]
    fit = []
    for f in range(len(bpos)):
        b = bpos[f, bi] - bpos[f, bi].mean(0)
        p = pose[f, pi] - pose[f, pi].mean(0)
        fit.append(R.align_vectors(p, b)[0])
    fit = R.concatenate(fit)
    smooth = R.concatenate([fit[max(0, f - window // 2):f + window // 2 + 1].mean() for f in range(len(fit))])
    turn = smooth[ref].inv() * smooth  # in the BVH frame; identity at ref
    n = bworld.shape[1]
    bworld = (R.from_quat(np.repeat(turn.as_quat(), n, 0)) * R.from_quat(bworld.reshape(-1, 4))).as_quat().reshape(bworld.shape)
    root = bpos[:, :1]
    bpos = root + np.stack([turn[f].apply(bpos[f] - root[f]) for f in range(len(bpos))])
    print(f"body turned from pose: up to {np.degrees(turn.magnitude()).max():.0f} deg from frame {ref}")
    return bpos, bworld


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rig"); ap.add_argument("bvh"); ap.add_argument("out"); ap.add_argument("clip")
    ap.add_argument("--start", type=int, default=0); ap.add_argument("--end", type=int)
    ap.add_argument("--fps", type=int)
    ap.add_argument("--pose", help="MoCapAnything *_pose_pred.npy: take the body's orientation from it")
    ap.add_argument("--lift", help="per-frame root lift in GLB world units (+Y), from lift.py")
    a = ap.parse_args()

    doc, binary = read_glb(a.rig)
    nodes = doc["nodes"]
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    joints = doc["skins"][0]["joints"]
    order = []  # every node in parent-first order
    def walk(i):
        order.append(i)
        for c in nodes[i].get("children", []): walk(c)
    for s in doc["scenes"][doc.get("scene", 0)]["nodes"]: walk(s)

    rest_rot, rest_pos, rest_scale = {}, {}, {}
    for i in order:
        t, r, s = node_trs(nodes[i])
        if i in parent:
            p = parent[i]
            rest_pos[i] = rest_pos[p] + rest_rot[p].apply(rest_scale[p] * t)
            rest_rot[i] = rest_rot[p] * r
            rest_scale[i] = rest_scale[p] * s
        else:
            rest_pos[i], rest_rot[i], rest_scale[i] = t, r, s

    names, bparents, brest, bpos, bworld, bfps = read_bvh(a.bvh)
    if a.pose:
        bpos, bworld = orient_from_pose(names, bpos, bworld, np.load(a.pose), a.start)
    # MoCapAnything's root heading is relative to the video camera; face the rig's own forward at the
    # first frame (yaw about BVH +Y only), keeping any turn after it.
    yaw = R.from_quat(bworld[a.start, 0]).as_euler("YXZ")[0]
    face = R.from_euler("Y", -yaw)
    bworld = (face * R.from_quat(bworld.reshape(-1, 4))).as_quat().reshape(bworld.shape)
    bpos = face.apply(bpos.reshape(-1, 3)).reshape(bpos.shape)
    print(f"removed camera heading {np.degrees(yaw):.1f} deg")
    fps = a.fps or bfps
    end = a.end if a.end is not None else len(bpos) - 1
    frames = range(a.start, end + 1)
    by_name = {nodes[j]["name"]: j for j in joints}
    common = [(by_name[n], k) for k, n in enumerate(names) if n in by_name]
    missing = sorted(set(by_name) - set(names))
    print(f"{len(common)} of {len(joints)} rig joints matched; unmatched: {missing}")

    g = kabsch(np.array([rest_pos[j] for j, _ in common]), brest[[k for _, k in common]])
    ginv = g.inv()
    size = lambda p: np.linalg.norm(p - p.mean(0), axis=1).mean()
    unit = size(np.array([rest_pos[j] for j, _ in common])) / size(brest[[k for _, k in common]])
    root = next(j for j in joints if parent.get(j) not in joints)
    broot = bpos[:, names.index(nodes[root]["name"])]
    print(f"rest fit {g.as_rotvec(degrees=True).round(1)} deg, unit {unit:.4g}, root {nodes[root]['name']}")

    bone_of = dict(common)
    lift = np.load(a.lift) if a.lift else np.zeros(len(frames))
    rot_keys = {j: [] for j in joints}
    root_keys = []
    for f in frames:
        world = dict(rest_rot)
        for i in order:
            if i in bone_of:
                k = bone_of[i]
                delta = R.from_quat(bworld[f, k])  # BVH rest world rotations are identity
                world[i] = ginv * delta * g * rest_rot[i]
            elif i in parent and parent[i] in world and i in joints:
                world[i] = world[parent[i]] * R.from_quat(nodes[i].get("rotation", [0, 0, 0, 1]))
        for j in joints:
            rot_keys[j].append((world[parent[j]].inv() * world[j]).as_quat())
        move = ginv.apply(broot[f] - broot[frames[0]]) * unit + [0, lift[f - frames[0]], 0]
        p = parent[root]
        t0, _, _ = node_trs(nodes[root])
        root_keys.append(t0 + rest_rot[p].inv().apply(move) / rest_scale[p])

    times = np.arange(len(frames), dtype="<f4") / fps
    def add(arr, typ, minmax=False):
        arr = np.ascontiguousarray(arr, dtype="<f4")
        off = len(binary) + (-len(binary) % 4)
        binary.extend(b"\0" * (off - len(binary))); binary.extend(arr.tobytes())
        doc["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes})
        acc = {"bufferView": len(doc["bufferViews"]) - 1, "componentType": 5126, "count": len(arr), "type": typ}
        if minmax: acc |= {"min": [float(arr.min())], "max": [float(arr.max())]}
        doc["accessors"].append(acc)
        return len(doc["accessors"]) - 1
    t_acc = add(times, "SCALAR", minmax=True)
    anim = {"name": a.clip, "samplers": [], "channels": []}
    def channel(node, path, values, typ):
        anim["samplers"].append({"input": t_acc, "output": add(values, typ), "interpolation": "LINEAR"})
        anim["channels"].append({"sampler": len(anim["samplers"]) - 1, "target": {"node": node, "path": path}})
    for j in joints:
        q = np.array(rot_keys[j])
        for n in range(1, len(q)):  # keep quaternions on one hemisphere so LINEAR does not flip
            if np.dot(q[n], q[n - 1]) < 0: q[n] = -q[n]
        channel(j, "rotation", q, "VEC4")
    channel(root, "translation", np.array(root_keys), "VEC3")
    doc["animations"] = [x for x in doc["animations"] if x["name"] != a.clip] + [anim]
    write_glb(a.out, doc, binary)
    print(f"wrote {a.out}: clip {a.clip}, {len(frames)} frames at {fps} fps")


if __name__ == "__main__":
    main()
