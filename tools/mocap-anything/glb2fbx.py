# blender -b -P glb2fbx.py -- rig.glb OUTDIR NAME clip1,clip2,...
# Quaternius GLB -> the FBX layout MoCapAnything's custom-rig pipeline reads: NAME.fbx (base, first
# clip) plus NAME-<clip>.fbx. Bakes the armature's object scale into the bones (their BVH export ignores
# object scale) at roughly Truebones size (cm), and drops glTF import extras (bone shape, _end empties).
import bpy, sys
a = sys.argv[sys.argv.index("--") + 1:]
src, out, name, clips = a[0], a[1], a[2], a[3].split(",")
LENGTH = 120.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for o in list(bpy.data.objects):
    if o.type == "EMPTY" and o.parent is arm or (o.type == "MESH" and o.parent is not arm):
        bpy.data.objects.remove(o)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
for i, o in enumerate(meshes): o.name = f"{name}Mesh{i}"
root = arm.parent
arm.parent = None
if root: bpy.data.objects.remove(root)
bpy.context.view_layer.update()
k = LENGTH / max(arm.dimensions)
arm.scale = [s * k for s in arm.scale]
grow = arm.scale[0]
bpy.ops.object.select_all(action="DESELECT")
for o in [arm, *meshes]: o.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
for act in bpy.data.actions:
    for fc in act.fcurves:
        if fc.data_path.endswith(".location"):
            for kp in fc.keyframe_points:
                kp.co.y *= grow; kp.handle_left.y *= grow; kp.handle_right.y *= grow
bpy.context.view_layer.update()
arm.scale = (0.01, 0.01, 0.01)  # Truebones FBXs import as cm bones under a 0.01 object scale
bpy.context.view_layer.update()
print("dims", tuple(round(x, 1) for x in arm.dimensions), "bone scale", grow)
acts = {x.name: x for x in bpy.data.actions}
def export(path, action):
    arm.animation_data_create()
    arm.animation_data.action = action
    s, e = action.frame_range
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = int(s), int(e)
    bpy.ops.export_scene.fbx(filepath=path, add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=False,
                             bake_anim_use_nla_strips=False, armature_nodetype="NULL")
export(f"{out}/{name}.fbx", acts[clips[0] + "_AnimalArmature"])
for c in clips:
    export(f"{out}/{name}-{c}.fbx", acts[c + "_AnimalArmature"])
