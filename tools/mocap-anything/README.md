# Clips from video with MoCapAnything V2

Turn a video of an animal into a new clip on a rig Sprute already plays on its own body (such as the
Quaternius husky), then animate a character with it.

```
blender -b -P glb2fbx.py -- husky.glb Truebone_Z-OO/Husky Husky Idle,Walk,Gallop,Attack,Gallop_Jump
# in a MoCapAnything checkout (github.com/phongdaot/MocapAnything), with videos/Husky#pounce.mp4:
bash examples/custom_rig/run.sh Husky
python -m inference.video2pose2rot --config examples/custom_rig/inference.yaml
python bvh2glb.py husky.glb outputs/custom_rig/videos/Husky#pounce/Husky_Husky_rot6d_pred.bvh husky-pounce.glb Pounce --fps 24 --start 72 --end 117
sprute animate character --character dusk.directions.png --motion husky-pounce.glb --clip Pounce --directions 4
```

- `glb2fbx.py` writes the FBX layout the custom-rig preprocessing reads, in Truebones' units. A GLB exported
  straight from Blender fails it (object scale, a mesh named `Cube`, no action on the base).
- `bvh2glb.py` appends the predicted motion to the GLB as a clip. It removes the camera heading MoCapAnything
  leaves on the root. `--fps` is the input video's rate; the BVH header says 30 whatever the video was.
