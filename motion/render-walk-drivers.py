"""Run inside Blender: --background --factory-startup --disable-autoexec --python THIS -- --model FILE --output NEW_FOLDER."""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector

MODEL_SHA256 = '1b7bf67866360665426bb99e4c71bd619f19b408453c24e30f0c3071601eee5c'
DIRECTIONS = ['S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW']
FACINGS = [
    'toward the camera in front view',
    'diagonally toward the lower right in front three-quarter view',
    'right in strict side profile',
    'diagonally away toward the upper right in rear three-quarter view',
    'away from the camera in rear view',
    'diagonally away toward the upper left in rear three-quarter view',
    'left in strict side profile',
    'diagonally toward the lower left in front three-quarter view',
]


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Render the pinned CC0 Quaternius walk as eight direction-matched WAN drivers.')
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--scail-masks', action='store_true', help='Also render source alpha and encode lossless SCAIL motion masks')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    model, output = args.model.resolve(strict=True), args.output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f'Output already exists: {output}')
    if sha(model) != MODEL_SHA256:
        raise ValueError('Model does not match the supported Quaternius Standard GLB. See motion/README.md; other rigs are not supported by this profile.')
    ffmpeg = shutil.which(args.ffmpeg)
    if not ffmpeg:
        raise ValueError('FFmpeg not found; install it or pass --ffmpeg /path/to/ffmpeg')
    # Validate dependencies before rendering. All subprocess arguments remain separate.
    subprocess.run([ffmpeg, '-version'], check=True, stdout=subprocess.DEVNULL)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(model))
    rig, action = bpy.data.objects['Rig'], bpy.data.actions['Walk_Loop']
    if list(action.frame_range) != [0.0, 32.0]:
        raise ValueError('Unexpected Walk_Loop range')
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    rig.animation_data.action = action
    rig.animation_data.action_slot = action.slots[0]
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj.name != 'Mannequin':
            obj.hide_render = True
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.fps_base = 1
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = False
    shading = scene.display.shading
    shading.light, shading.color_type = 'STUDIO', 'SINGLE'
    shading.single_color = (0.32, 0.5, 0.66)
    shading.show_shadows, shading.show_cavity = False, True
    shading.background_type = 'WORLD'
    scene.world.color = (0.78, 0.78, 0.78)
    scene.view_settings.view_transform = 'Standard'
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type, camera.data.ortho_scale = 'ORTHO', 2.6
    scene.camera = camera
    target = Vector((0, 0, .9))

    def pose_values():
        return {b.name: [float(v) for row in b.matrix for v in row] for b in rig.pose.bones}

    scene.frame_set(0)
    first_pose = pose_values()
    scene.frame_set(32)
    last_pose = pose_values()
    seam = max(abs(a - b) for name in first_pose for a, b in zip(first_pose[name], last_pose[name]))
    if seam > 1e-6:
        raise ValueError(f'Source pose does not close: {seam}')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.sprute-drivers-', dir=output.parent))
    try:
        views, bones = {}, []
        for frame in range(32):
            scene.frame_set(frame)
            bones.append({'frame': frame, 'time': frame / 24, 'bones': {b.name: {'head': list(rig.matrix_world @ b.head), 'tail': list(rig.matrix_world @ b.tail)} for b in rig.pose.bones if any(k in b.name.lower() for k in ['foot', 'toe', 'hips', 'spine'])}})
            for index, direction in enumerate(DIRECTIONS):
                angle = index * math.pi / 4
                z = .9 + 6 * math.tan(math.radians(30)) if direction == 'S' else 2.5
                camera.location = Vector((-6 * math.sin(angle), -6 * math.cos(angle), z))
                camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
                folder = temporary / direction / 'frames'
                folder.mkdir(parents=True, exist_ok=True)
                scene.render.filepath = str(folder / f'{frame + 1:06d}.png')
                scene.render.film_transparent = False
                bpy.ops.render.render(write_still=True)
                if args.scail_masks:
                    alpha_folder = temporary / direction / 'mask-source'
                    alpha_folder.mkdir(parents=True, exist_ok=True)
                    scene.render.film_transparent = True
                    scene.render.filepath = str(alpha_folder / f'{frame + 1:06d}.png')
                    bpy.ops.render.render(write_still=True)
        for index, direction in enumerate(DIRECTIONS):
            folder = temporary / direction
            shutil.copyfile(folder / 'frames/000001.png', folder / 'first.png')
            subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-n', '-framerate', '24', '-i', str(folder / 'frames/%06d.png'), '-vf', 'loop=loop=2:size=32:start=0', '-frames:v', '65', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', str(folder / 'driver.mp4')], check=True)
            views[direction] = {'video': f'{direction}/driver.mp4', 'firstFrame': f'{direction}/first.png', 'videoSha256': sha(folder / 'driver.mp4'), 'firstFrameSha256': sha(folder / 'first.png'), 'caption': f'A blue humanoid mannequin walking in place facing {FACINGS[index]}. Alternating steps, gentle knee bends and opposing arm movement on a plain light gray background.'}
            if args.scail_masks:
                # Threshold the blue RGB channel explicitly after alpha extraction.
                # A luma-only LUT can be negotiated as RGB and leave blue unthresholded.
                mask_filter = "alphaextract,format=rgb24,lutrgb=r=0:g=0:b='if(gte(val,128),255,0)',loop=loop=2:size=32:start=0"
                subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-n', '-framerate', '24', '-i', str(folder / 'mask-source/%06d.png'), '-vf', mask_filter, '-frames:v', '65', '-c:v', 'ffv1', '-pix_fmt', 'bgr0', str(folder / 'mask.mkv')], check=True)
                views[direction].update({'maskVideo': f'{direction}/mask.mkv', 'maskVideoSha256': sha(folder / 'mask.mkv'), 'maskEncoding': 'blue-on-black-source-alpha-ge128-ffv1-v1'})
        metadata = {'version': 1, 'profile': 'quaternius-standard-walk-8dir-v1', 'pathScope': 'local-bundle-relative', 'sourceModelSha256': MODEL_SHA256, 'sourceLicense': 'CC0-1.0', 'sourceCreator': 'Quaternius', 'blenderVersion': bpy.app.version_string, 'width': 512, 'height': 512, 'fps': 24, 'sourceFrames': list(range(32)), 'videoFrameCount': 65, 'endpointPoseMatrixMaxAbsDifference': seam, 'frontElevationDegrees': 30, 'otherElevationDegrees': math.degrees(math.atan2(1.6, 6)), 'views': views, 'reviewStatus': 'unreviewed', 'note': 'Local paths must be installed on the ComfyUI server before planning. Shared source phase is not proof of target gait, contact or seamless WAN output.'}
        (temporary / 'bundle.json').write_text(json.dumps(metadata, indent=2) + '\n')
        (temporary / 'source-bones.json').write_text(json.dumps(bones, indent=2) + '\n')
        shutil.copyfile(Path(__file__).with_name('QUATERNIUS-LICENSE.txt'), temporary / 'LICENSE.txt')
        output.mkdir()
        try:
            temporary.rename(output)
        except Exception:
            output.rmdir()
            raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    print(f'Saved eight local drivers to {output}. Review before WAN use.')


main()
