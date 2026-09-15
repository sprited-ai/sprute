"""Explicit experimental head conditioning; no automatic visibility inference.

Input uses One-to-All's normalized dwpose arrays. Functions own their outputs
and preserve the caller's poses. Requires NumPy, not the model runtime.
"""
from copy import deepcopy
import numpy as np

HEAD = (0, 14, 15, 16, 17)
POLICIES = ('reference-head', 'hidden-head')


def _validate(pose):
    body = pose['bodies']
    candidate = body['candidate']
    count = len(candidate)
    if count not in (18, 20):
        raise ValueError('Expected 18 body points or 20 including toes')
    for key, shape in [('candidate', (count, 2)), ('score', (1, count)), ('subset', (1, count))]:
        value = body[key]
        if not isinstance(value, np.ndarray) or value.shape != shape or not np.isfinite(value).all():
            raise ValueError(f'Expected finite bodies.{key} array with shape {shape}')
    face = pose['faces']
    score = pose['faces_score']
    if not isinstance(face, np.ndarray) or face.shape != (1, 68, 2) or not np.isfinite(face).all():
        raise ValueError('Expected finite faces array with shape (1, 68, 2)')
    if not isinstance(score, np.ndarray) or score.shape != (1, 68) or not np.isfinite(score).all():
        raise ValueError('Expected finite faces_score array with shape (1, 68)')


def reference_head(reference, frames):
    """Translate reference head/face with each neck, retaining body/hand motion.

This imposes a fixed head relative to the neck; it does not animate head turns.
Coordinates and confidence are replaced together, as in experiment 289.
"""
    _validate(reference)
    result = []
    indices = list(HEAD)
    for frame in frames:
        _validate(frame)
        output = deepcopy(frame)
        delta = frame['bodies']['candidate'][1] - reference['bodies']['candidate'][1]
        output['bodies']['candidate'][indices] = reference['bodies']['candidate'][indices] + delta
        for key in ('score', 'subset'):
            output['bodies'][key][:, indices] = reference['bodies'][key][:, indices]
        output['faces'] = reference['faces'] + delta
        output['faces_score'] = reference['faces_score'].copy()
        result.append(output)
    return result


def drawing_pose(pose, *, policy):
    """Return a copy for rendering and whether to omit dense face points.

Use on BOTH reference and driving poses. reference-head keeps head markers;
reference-image dense face suppression remains the upstream caller's choice.
hidden-head removes all incident head lines as well as points, matching 292.
"""
    if policy not in POLICIES:
        raise ValueError(f'Choose an explicit head policy from {POLICIES}')
    _validate(pose)
    output = deepcopy(pose)
    hidden = policy == 'hidden-head'
    if hidden:
        output['bodies']['subset'][:, list(HEAD)] = -1
        output['bodies']['score'][:, list(HEAD)] = 0
        output['faces_score'][:] = 0
    return output, hidden
