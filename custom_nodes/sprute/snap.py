"""Snap a motion's length to a multiple of every frames, so keeping every Nth frame lands on its ends.

A loop then wraps by a whole step; a clip that doesn't loop ends on a kept frame, at its last pose.
"""


def cycle_frames(seconds: float, fps: float, every: int) -> int:
    """Frames the motion spans at fps, rounded to a multiple of every."""
    return every * max(1, round(seconds * fps / every))


def seconds(motion) -> float:
    """How long the motion lasts. A loop's last key comes back to its first; a clip's last key is its last pose."""
    _, motion_fps, loop, _, hips, *_ = motion
    return (len(hips) if loop else len(hips) - 1) / motion_fps


def snapped_fps(motion, fps: float, every: int) -> float:
    """The frame rate that fits the motion into those frames; fps as given for a single pose, or every of 0."""
    length = seconds(motion)
    if every == 0 or length <= 0:
        return fps
    return cycle_frames(length, fps, every) / length


def time_scale(motion, fps: float, every: int) -> float:
    """How many times as long the snapped motion plays at fps as it lasts."""
    return snapped_fps(motion, fps, every) / fps


def keep_frames(motion, fps: float, every: int, frames: int) -> int:
    """How many of the frames rendered to keep once snapped: one cycle of a loop, or a clip up to its last pose.

    All of them otherwise: unsnapped, the motion's end falls between frames, and one longer than frames doesn't fit.
    """
    _, _, loop, *_ = motion
    length = seconds(motion)
    if every == 0 or length <= 0:
        return frames
    # A loop's last frame is its first again; a clip's is its last pose.
    return min(frames, cycle_frames(length, fps, every) + (0 if loop else 1))
