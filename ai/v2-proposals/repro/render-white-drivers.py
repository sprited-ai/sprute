import bpy,math,json,time,hashlib
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
R=Path(__file__).resolve().parent;E=Path('/Users/jin/dev/sprute/experiments');base=E/'477-white-driver/render-white/driver.blend'
views={'S':0,'SE':45,'E':90,'NE':135,'N':180,'NW':225,'W':270,'SW':315}
for state,donor in [('idle',E/'468-chibi-run-idle/idle-driver/driver.blend'),('walk',E/'457-chibi1/driver-shade75/driver.blend')]:
 bpy.ops.wm.open_mainfile(filepath=str(donor));scene=bpy.context.scene;rig=bpy.data.objects['VRM_Target'];names=[b.name for b in rig.data.bones];rest={b.name:b.matrix_local.copy() for b in rig.data.bones};world=rig.matrix_world.copy();poses=[];fps=scene.render.fps
 for f in range(scene.frame_start,scene.frame_end+1):
  scene.frame_set(f);poses.append({n:rig.pose.bones[n].matrix_basis.copy() for n in names})
 bpy.ops.wm.open_mainfile(filepath=str(base));scene=bpy.context.scene;rig=bpy.data.objects['VRM_Target']
 err=max(abs(rest[n][i][j]-rig.data.bones[n].matrix_local[i][j]) for n in names for i in range(4) for j in range(4));assert err<1e-5,err
 print('RIG_WORLD donor',list(map(list,world)),'base',list(map(list,rig.matrix_world)),flush=True)
 # Keep the run scene object transform; transfer only local bone animation.
 rig.animation_data_clear()
 for f,pose in enumerate(poses):
  for n,m in pose.items():
   b=rig.pose.bones[n];b.rotation_mode='QUATERNION';b.matrix_basis=m
   for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(data_path=prop,frame=f,group=n)
 scene.frame_start=0;scene.frame_end=len(poses)-1;scene.render.fps=fps
 camera=scene.camera;forward=camera.rotation_euler.to_quaternion()@Vector((0,0,-1));distance=math.hypot(camera.location.x,camera.location.y)/math.hypot(forward.x,forward.y);center=camera.location+forward*distance;height=camera.data.ortho_scale*.8
 out=R/state;out.mkdir(exist_ok=True)
 metadata={'state':state,'render_scene':str(base),'motion_scene':str(donor),'frames':len(poses),'fps':fps,'rig_rest_error':err,'camera_elevation':15,'ortho_scale':camera.data.ortho_scale,'resolution':[scene.render.resolution_x,scene.render.resolution_y],'base_sha256':hashlib.sha256(base.read_bytes()).hexdigest()};(out/'metadata.json').write_text(json.dumps(metadata,indent=2))
 for d,degrees in views.items():
  angle=math.radians(degrees);camera.location=center+Vector((-math.sin(angle)*height*4,-math.cos(angle)*height*4,math.tan(math.radians(15))*height*4));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
  if scene.get('cameraLighting',False):
   rotation=Quaternion(Vector((0,0,1)),-angle)
   for light in (o for o in scene.objects if o.type=='LIGHT' and 'cameraLightBasePosition' in o):
    light.location=center+rotation@(Vector(light['cameraLightBasePosition'])-center);light.rotation_euler=(Vector((0,0,height*.55))-light.location).to_track_quat('-Z','Y').to_euler()
  folder=out/'cells'/d;folder.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(folder/'######');print('PROGRESS',state,d,flush=True);bpy.ops.render.render(animation=True)
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'driver.blend'))
 print('DONE',state,flush=True)
