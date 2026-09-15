"""Experimental Z-up world-space arm adjustment, before scaling/projection."""
import numpy as np


def reduce_abduction(arms, *, retained_fraction):
    """Copy Nx2x3x3 points: frame, right/left, shoulder/elbow/wrist, XYZ.

    Rotate each elbow/wrist pair rigidly about its shoulder to retain the given
    fraction of upper-arm lateral angle. The horizontal shoulder axis and world
    down define the rotation plane. This is for upright humanoid geometry; it is
    not an IK solver, collision check, or a general anatomical retargeter.
    """
    points = np.asarray(arms, dtype=float)
    if points.ndim != 4 or points.shape[1:] != (2, 3, 3) or not len(points):
        raise ValueError('Expected nonempty Nx2x3x3 arm points')
    if not np.isfinite(points).all():
        raise ValueError('Arm points must be finite')
    if (isinstance(retained_fraction, (bool, np.bool_)) or
            not np.isscalar(retained_fraction) or
            not np.isfinite(retained_fraction) or not 0 <= retained_fraction <= 1):
        raise ValueError('retained_fraction must be a number between 0 and 1')
    out = points.copy()
    down = np.array([0., 0., -1.])
    for frame, pair in enumerate(points):
        lateral = pair[1, 0] - pair[0, 0]
        lateral[2] = 0
        width = np.linalg.norm(lateral)
        if width < 1e-8:
            raise ValueError('Horizontal shoulder axis is degenerate')
        lateral /= width
        for side, p in enumerate(pair):
            if np.any(np.linalg.norm(np.diff(p, axis=0), axis=1) < 1e-8):
                raise ValueError('Arm segment is degenerate')
            upper = p[1] - p[0]
            a, b = upper @ lateral, upper @ down
            if np.hypot(a, b) < 1e-8:
                raise ValueError('Upper arm has no lateral/down component')
            if retained_fraction == 1:
                continue
            alpha = np.arctan2(a, b)
            theta = alpha * (1 - retained_fraction)
            def rotate(v):
                a, b = v @ lateral, v @ down
                return (v + lateral * (a*np.cos(theta)-b*np.sin(theta)-a)
                        + down * (a*np.sin(theta)+b*np.cos(theta)-b))
            out[frame, side] = [p[0], p[0]+rotate(p[1]-p[0]),
                                p[0]+rotate(p[2]-p[0])]
    return out
