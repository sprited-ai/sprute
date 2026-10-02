"""Adapt Kimodo's SOMA motion to the existing Template-kun renderer."""
import numpy as np

from . import motion_file, retarget


# SOMA names differ from Mixamo most notably at the spine and legs.
BONES = {name: name for name in retarget.BONES}
BONES.update(Spine="Spine1", Spine1="Spine2", Spine2="Chest", Neck="Neck1",
             LeftUpLeg="LeftLeg", LeftLeg="LeftShin",
             RightUpLeg="RightLeg", RightLeg="RightShin")


def adapt(motion, model_path):
    """Return one finite, in-place clip; generated motion is not assumed to loop."""
    names = list(motion.joint_names)
    missing = set(BONES.values()) - set(names)
    if missing:
        raise ValueError(f"Kimodo skeleton is missing: {', '.join(sorted(missing))}")
    rotations = np.asarray(motion.output_dict["global_rot_mats"])
    roots = np.asarray(motion.output_dict["root_positions"])
    neutral = np.asarray(motion.neutral_joints)
    if rotations.ndim != 5 or rotations.shape[0] != 1 or rotations.shape[2:] != (len(names), 3, 3):
        raise ValueError("Kimodo must produce exactly one sample of joint rotation matrices")
    rotations, roots = rotations[0], roots[0]
    if len(rotations) < 2 or roots.shape != (len(rotations), 3):
        raise ValueError("Kimodo root positions must match the generated frames")
    if neutral.shape != (len(names), 3):
        raise ValueError("Kimodo must provide its neutral skeleton")
    if not all(np.isfinite(a).all() for a in (rotations, roots, neutral)):
        raise ValueError("Kimodo motion contains non-finite values")
    fps = float(motion.fps)
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError("Kimodo frame rate must be positive")
    target = retarget.Skeleton(model_path)
    height = neutral[names.index("Hips"), 1] - neutral[:, 1].min()
    if height <= 0:
        raise ValueError("Kimodo neutral skeleton has no positive hip height")
    # Hold horizontal travel in place; preserve vertical jumps/crouches at the
    # target character's proportions. All eight cameras see the same motion.
    offsets = np.zeros_like(roots)
    # SOMA neutral joints are hip-centred, while generated roots are measured
    # from the floor. Subtract standing hip height, not neutral Hips.y (zero).
    offsets[:, 1] = roots[:, 1] - height
    offsets *= target.rest[target.hips, 1, 3] / height
    turns = [{target.bone[name]: frame[names.index(source)] for name, source in BONES.items()}
             for frame in rotations]
    local, hips = motion_file.local_motion(target.pose, target.parents, target.hips, turns, offsets)
    by_index = {index: name for name, index in target.bone.items()}
    return "kimodo", fps, False, {by_index[node]: values for node, values in local.items()}, hips
