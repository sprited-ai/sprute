"""Split a TRELLIS.2 Monet mesh (one fused surface) into body, hair, skirt and bow, by baked colour and height, then a
neighbour vote so the cuts follow the part boundaries instead of speckling.

    Blender -b -P tools/monet3d/split_parts.py -- MESH.glb OUT.glb [DEBUG.glb]

OUT.glb keeps the baked texture on four objects; DEBUG.glb paints each part one flat colour for turntable.py.
Heights are fractions of her standing height, read off the A-pose front drawing (docs/monet-3d.md).
"""
import sys, colorsys
import bpy, bmesh
import numpy as np

args = sys.argv[sys.argv.index("--") + 1:]
glb, out = args[:2]
debug = args[2] if len(args) > 2 else None
PARTS = ["body", "hair", "skirt", "bow"]
FLAT = [(0.85, 0.75, 0.65, 1), (1.0, 0.8, 0.1, 1), (0.2, 0.6, 0.3, 1), (0.8, 0.1, 0.6, 1)]
WAIST, SHOULDER, BOW = 0.49, 0.62, 0.86

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
o = next(o for o in bpy.context.scene.objects if o.type == "MESH")
me = o.data
img = next(n.image for n in o.material_slots[0].material.node_tree.nodes if n.type == "TEX_IMAGE")
W, H = img.size
px = np.array(img.pixels[:]).reshape(H, W, 4)[..., :3]

n = len(me.polygons)
uv = np.zeros(len(me.loops) * 2); me.uv_layers.active.data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get("co", co)
co = co.reshape(-1, 3) @ np.array(o.matrix_world)[:3, :3].T
vi = np.zeros(len(me.loops), int); me.loops.foreach_get("vertex_index", vi)
ls = np.zeros(n, int); me.polygons.foreach_get("loop_start", ls)
fuv = (uv[ls] + uv[ls + 1] + uv[ls + 2]) / 3
pos = (co[vi[ls]] + co[vi[ls + 1]] + co[vi[ls + 2]]) / 3
rgb = px[np.clip((fuv[:, 1] * H).astype(int), 0, H - 1), np.clip((fuv[:, 0] * W).astype(int), 0, W - 1)]
hsv = np.array([colorsys.rgb_to_hsv(*c) for c in rgb])
hue, sat, val = hsv[:, 0] * 360, hsv[:, 1], hsv[:, 2]
z = (pos[:, 2] - pos[:, 2].min()) / np.ptp(pos[:, 2])

golden = (hue >= 30) & (hue < 60) & (sat > 0.45)
skin = (hue >= 10) & (hue < 35) & (sat < 0.5) & (val > 0.55)
bowish = (hue < 15) | (hue >= 330) | ((hue >= 180) & (hue < 270))

label = np.zeros(n, int)
# the skirt is the band from its hem to the waist; the hem is found, not guessed: the lowest height where the
# figure's outline flares out to the skirt's width
slice_ = np.clip((z * 100).astype(int), 0, 100)
r = np.hypot(pos[:, 0] - np.median(pos[:, 0]), pos[:, 1] - np.median(pos[:, 1]))
rmax = np.zeros(101); np.maximum.at(rmax, slice_, r)
low = np.arange(10, 50)
hem = low[rmax[low] > 0.7 * rmax[low].max()].min() / 100
print("hem at", hem)
band = (z >= hem) & (z < WAIST)
# the print has cream and pink flowers that read as skin, so colour only takes out the hands, which hang past the
# skirt's upper half in the A-pose; near the hem the legs stand inside the skirt's outer shell
x = np.abs(pos[:, 0] - np.median(pos[band, 0]))
hands = skin & (z > hem + 0.4 * (WAIST - hem)) & (x > 0.6 * x[band].max())
legs = (z < hem + 0.05) & (r < 0.5 * rmax[slice_])
label[band & ~hands & ~legs] = 2
label[golden & (z > WAIST)] = 1
label[bowish & (z > BOW)] = 3

# neighbour vote over shared edges
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
pairs = np.array([(e.link_faces[0].index, e.link_faces[1].index) for e in bm.edges if len(e.link_faces) == 2])
bm.free()
for _ in range(12):
    votes = np.zeros((n, len(PARTS)))
    np.add.at(votes, (pairs[:, 0], label[pairs[:, 1]]), 1)
    np.add.at(votes, (pairs[:, 1], label[pairs[:, 0]]), 1)
    votes[np.arange(n), label] += 1.5
    label = votes.argmax(1)
print("faces per part", {p: int((label == i).sum()) for i, p in enumerate(PARTS)})


def split(paint):
    for i, part in enumerate(PARTS):
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.duplicate()
        d = bpy.context.active_object
        d.name = part
        bm = bmesh.new(); bm.from_mesh(d.data); bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if label[f.index] != i], context="FACES")
        bm.to_mesh(d.data); bm.free()
        if paint:
            m = bpy.data.materials.new(part); m.use_nodes = True
            next(nd for nd in m.node_tree.nodes if nd.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = FLAT[i]
            d.data.materials.clear(); d.data.materials.append(m)
    o.hide_set(True); o.hide_render = True
    bpy.ops.object.select_all(action="DESELECT")
    for part in PARTS:
        bpy.data.objects[part].select_set(True)


for path, paint in [(out, False)] + ([(debug, True)] if debug else []):
    for part in PARTS:
        if part in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[part])
    o.hide_set(False)
    split(paint)
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True)
