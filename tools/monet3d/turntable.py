"""Render a GLB from 8 directions into one contact sheet, emission-lit so we judge shape and baked colour only.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P tools/monet3d/turntable.py -- MESH.glb OUT.png
"""
import math, sys
import bpy
from mathutils import Vector

glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
corners = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector(min(c[i] for c in corners) for i in range(3))
hi = Vector(max(c[i] for c in corners) for i in range(3))
centre, height = (lo + hi) / 2, max(hi - lo)

# baked colour straight to the screen: TRELLIS bakes de-lit albedo, so emission shows exactly what it made
for o in meshes:
    for slot in o.material_slots:
        nodes, links = slot.material.node_tree.nodes, slot.material.node_tree.links
        bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
        emit = nodes.new("ShaderNodeEmission")
        src = bsdf.inputs["Base Color"].links
        if src:
            links.new(src[0].from_socket, emit.inputs["Color"])
        outp = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
        links.new(emit.outputs[0], outp.inputs["Surface"])

scene = bpy.context.scene
scene.render.resolution_x = scene.render.resolution_y = 512
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new("w"); scene.world.color = (1, 1, 1)
scene.view_settings.view_transform = "Standard"
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam); scene.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = height * 1.1

import os, tempfile
tiles = []
tmp = tempfile.mkdtemp()
for i in range(8):
    a = math.radians(45 * i)
    # glTF imports Y-up as Blender Z-up; the model faces -Y
    cam.location = centre + Vector((math.sin(a), -math.cos(a), 0.15)) * height * 3
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{tmp}/{i}.png"
    bpy.ops.render.render(write_still=True)
    tiles.append(bpy.data.images.load(scene.render.filepath))

W = 512
sheet = bpy.data.images.new("sheet", W * 4, W * 2)
px = [1.0] * (W * 4 * W * 2 * 4)
for i, t in enumerate(tiles):
    src = list(t.pixels)
    ox, oy = (i % 4) * W, (1 - i // 4) * W
    for y in range(W):
        row = (oy + y) * W * 4 * 4 + ox * 4
        px[row:row + W * 4] = src[y * W * 4:(y + 1) * W * 4]
sheet.pixels = px
sheet.filepath_raw = out; sheet.file_format = "PNG"; sheet.save()
