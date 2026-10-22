"""Snap a looping motion's cycle to a multiple of every frames, so keeping every Nth frame wraps by a whole step."""


def cycle_frames(seconds: float, fps: float, every: int) -> int:
    """Frames one cycle takes at fps, rounded to a multiple of every."""
    return every * max(1, round(seconds * fps / every))


def snapped_fps(motion, fps: float, every: int) -> float:
    """The frame rate that fits one cycle of a looping motion into those frames; fps as given otherwise."""
    _, motion_fps, loop, _, hips = motion
    if not loop:
        return fps
    seconds = len(hips) / motion_fps
    return cycle_frames(seconds, fps, every) / seconds


def time_scale(motion, fps: float, every: int) -> float:
    """How many times as long the snapped motion plays at fps as it lasts."""
    return snapped_fps(motion, fps, every) / fps
