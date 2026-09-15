"""Experimental normalized body-pose fitting; no model, renderer or file I/O."""
import copy
import numpy as np


def fit_body(reference, motion, *, fit_policy, vertical_lift, cycle_frames=32,
             min_shoulder_width=8 / 512):
    """Copy/fit Nx20x3 rig poses. Scores are availability, not probabilities.

    Policies must be chosen explicitly after inspecting the reference. The width
    guard is an experimental conditioning bound, not a learned quality threshold.
    Returned coordinates are not clipped: motion may extend outside the canvas.
    """
    ref = np.asarray(reference, dtype=float)
    pts = np.asarray(motion, dtype=float)
    if ref.shape != (20, 3) or pts.ndim != 3 or pts.shape[1:] != (20, 3):
        raise ValueError('Expected reference20x3 and motionNx20x3')
    if not np.isfinite(ref).all() or not np.isfinite(pts).all():
        raise ValueError('Pose coordinates and scores must be finite')
    if isinstance(cycle_frames, bool) or not isinstance(cycle_frames, int) or not 1 <= cycle_frames <= len(pts):
        raise ValueError('cycle_frames must select a nonempty available cycle')
    if fit_policy not in ('shoulder-width', 'uniform-envelope'):
        raise ValueError('Choose shoulder-width or uniform-envelope explicitly')
    if not np.isfinite(vertical_lift) or not 0 <= vertical_lift <= 1:
        raise ValueError('vertical_lift must be between0 and1')
    if not np.isfinite(min_shoulder_width) or min_shoulder_width <= 0:
        raise ValueError('min_shoulder_width must be positive')
    anchors = [2, 5, 10, 13]
    if np.any(ref[anchors, 2] <= 0) or np.any(pts[:cycle_frames, anchors, 2] <= 0):
        raise ValueError('Required shoulder/ankle anchors are unavailable')
    mean = pts[:cycle_frames, :, :2].mean(axis=0)
    source_center = mean[[2, 5]].mean(axis=0)
    target_center = ref[[2, 5], :2].mean(axis=0)
    ankle_y = np.percentile(pts[:cycle_frames, [10, 13], 1], 95)
    source_height = ankle_y - source_center[1]
    target_height = ref[[10, 13], 1].mean() - target_center[1]
    if source_height <= 1e-8 or target_height <= 1e-8:
        raise ValueError('Shoulder-to-ankle envelope must have positive height')
    sy = target_height / source_height
    width = abs(mean[5, 0] - mean[2, 0])
    if fit_policy == 'shoulder-width':
        if width < min_shoulder_width:
            raise ValueError('Projected shoulders too narrow; inspect profile fit')
        sx = abs(ref[5, 0] - ref[2, 0]) / width
    else:
        sx = sy
    if min(sx, sy) <= 0 or not np.isfinite([sx, sy]).all():
        raise ValueError('Fit scale must be finite and positive')
    offset = target_center - source_center * [sx, sy]
    out = pts.copy()
    out[:, 1:14, :2] = pts[:, 1:14, :2] * [sx, sy] + offset
    joints = [9, 10, 12, 13]
    low = out[:cycle_frames, joints, 1].max(axis=0)
    out[:, joints, 1] = low + vertical_lift * (out[:, joints, 1] - low)
    return out, {'fitPolicy': fit_policy, 'scale': [float(sx), float(sy)],
                 'offset': offset.tolist(), 'cycleFrames': cycle_frames,
                 'verticalLift': float(vertical_lift),
                 'sourceShoulderWidth': float(width)}


def prepare_metadata(reference, fitted_body, *, head_policy):
    """Return copied reference + motion metadata for the external renderer.

    reference-head preserves reference landmarks; apply head_policy.reference_head
    after dwpose conversion. hidden-head omits face markers in both streams.
    Both policies omit hand poses. Never infer visibility from direction or score.
    """
    if head_policy not in ('reference-head', 'hidden-head'):
        raise ValueError('Choose reference-head or hidden-head explicitly')
    ref = copy.deepcopy(reference)
    bodies = np.asarray(fitted_body, dtype=float)
    if bodies.ndim != 3 or bodies.shape[1:] != (20, 3) or len(bodies) == 0 or not np.isfinite(bodies).all():
        raise ValueError('Expected finite fitted bodyNx20x3')
    if np.asarray(ref['keypoints_body']).shape != (20, 3) or not np.isfinite(np.asarray(ref['keypoints_body'], dtype=float)).all():
        raise ValueError('Expected reference body20x3')
    empty = {}
    for key in ('keypoints_right_hand', 'keypoints_left_hand', 'keypoints_face'):
        value = np.asarray(ref[key], dtype=float)
        expected = (69, 3) if key == 'keypoints_face' else (21, 3)
        if value.shape != expected or not np.isfinite(value).all():
            raise ValueError(f'Invalid reference array: {key}')
        empty[key] = np.zeros_like(value).tolist()
    for key in ('keypoints_right_hand', 'keypoints_left_hand'):
        ref[key] = copy.deepcopy(empty[key])
    head = [0, 14, 15, 16, 17]
    if head_policy == 'hidden-head':
        ref['keypoints_body'] = np.asarray(ref['keypoints_body'], dtype=float).copy()
        ref['keypoints_body'][head] = 0
        ref['keypoints_body'] = ref['keypoints_body'].tolist()
        ref['keypoints_face'] = copy.deepcopy(empty['keypoints_face'])
    rows = []
    for body in bodies:
        row = copy.deepcopy(empty)
        body = body.copy()
        body[head] = 0  # hidden or replaced explicitly after dwpose conversion
        row['keypoints_body'] = body.tolist()
        rows.append(row)
    return ref, rows
