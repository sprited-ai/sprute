"""python lift.py RIG_CLIP.glb CLIP TRACK.npy START OUT.npy

Per-frame root lift (GLB world units, +Y) so the clip's lowest paw follows the subject's height above
the ground in the video. TRACK.npy holds per video frame (bbox bottom, top, left, right) of the matte;
the camera is assumed still and the first frames standing. Neither MoCapAnything output has height."""
import sys, json, struct
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp

glb, clip, track, start, out = sys.argv[1], sys.argv[2], np.load(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
raw = open(glb, "rb").read(); n = struct.unpack_from("<I", raw, 12)[0]
doc = json.loads(raw[20:20 + n]); binary = raw[28 + n:]
def acc(i):
    a = doc["accessors"][i]; v = doc["bufferViews"][a["bufferView"]]
    k = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[a["type"]]
    return np.frombuffer(binary, "<f4", a["count"] * k, v.get("byteOffset", 0) + a.get("byteOffset", 0)).reshape(-1, k)
nodes = doc["nodes"]; parent = {c: i for i, x in enumerate(nodes) for c in x.get("children", [])}
anim = next(x for x in doc["animations"] if x["name"] == clip)
chans = [(c["target"]["node"], c["target"]["path"], acc(anim["samplers"][c["sampler"]]["input"])[:, 0], acc(anim["samplers"][c["sampler"]]["output"])) for c in anim["channels"]]
frames = len(chans[0][2])
PAWS = ["FrontLowerLeg.L", "FrontLowerLeg.R", "BackLowerLeg.L", "BackLowerLeg.R"]
paw_ids = [next(i for i, x in enumerate(nodes) if x.get("name") == p) for p in PAWS]

def world(f):
    trs = {i: [np.array(x.get("translation", [0, 0, 0]), float), R.from_quat(x.get("rotation", [0, 0, 0, 1])), np.array(x.get("scale", [1, 1, 1]), float)] for i, x in enumerate(nodes)}
    if f is not None:
        for node, path, ts, vs in chans:
            if path == "rotation": trs[node][1] = R.from_quat(vs[f])
            elif path == "translation": trs[node][0] = vs[f].astype(float)
    pos, rot, sc = {}, {}, {}
    def walk(i):
        t, r, s = trs[i]
        if i in parent:
            p = parent[i]; pos[i] = pos[p] + rot[p].apply(sc[p] * t); rot[i] = rot[p] * r; sc[i] = sc[p] * s
        else: pos[i], rot[i], sc[i] = t, r, s
        for c in nodes[i].get("children", []): walk(c)
    for r0 in doc["scenes"][0]["nodes"]: walk(r0)
    return pos, rot, sc

# Paw tip: the lower-leg bone's head plus its rest length (to the ground in the rest pose) along its +Y.
pos, rot, sc = world(None)
ground = 0.0
length = {i: (pos[i][1] - ground) / rot[i].apply([0, 1, 0])[1] * -1 for i in paw_ids}
def lowest(f):
    pos, rot, sc = world(f)
    return min((pos[i] + rot[i].apply([0, length[i], 0]))[1] for i in paw_ids)
low = np.array([lowest(f) for f in range(frames)])
heads = [world(None)[0][next(i for i, x in enumerate(nodes) if x.get("name") == "Head")][1]]
stand_rig = heads[0] - ground

bottom, top = track[:, 0], track[:, 1]
ref = slice(start, start + 8)
stand_px = np.nanmedian(bottom[ref] - top[ref])
# Ground line in the image drifts as the subject moves (perspective); take it from the frames where the
# bbox bottom is at its lowest, i.e. paws down, as a straight line through start and end contacts.
v = np.arange(len(bottom)); contact = bottom >= np.nanpercentile(bottom, 60)
a, b = np.polyfit(v[contact], bottom[contact], 1)
height_px = np.clip(a * v + b - bottom, 0, None)
height = height_px[start:start + frames] / stand_px * stand_rig
lift = height - (low - ground)
print(f"paw lowest {low.min():.3f}..{low.max():.3f}, video height up to {height.max():.3f} "
      f"({height_px.max():.0f} px of {stand_px:.0f} px standing), lift {lift.min():.3f}..{lift.max():.3f}")
np.save(out, lift)
