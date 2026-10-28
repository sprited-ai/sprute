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

Real footage (tried on a border collie leap):

- Matte the subject onto white yourself first (BiRefNet works). MoCapAnything's own RMBG step keeps scenery on
  busy backgrounds and the model then poses the landscape.
- The rotation output keeps the body level and neither output has height. `bvh2glb.py --pose *_pose_pred.npy`
  takes the body's orientation from the position output; `lift.py` takes height from the matte's bounding box
  (still camera) for `--lift`. Even then a leap came out as a rear-up: the hind legs fold under in the air.
