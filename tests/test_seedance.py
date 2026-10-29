import numpy as np

from conftest import node_module

seedance = node_module("seedance")


def grid(frames, poses, line=False):
    """A 3x3 grid on gray with a white block per direction cell; poses picks each frame's block: 0 standing, 1 lying."""
    video = np.full((frames, 192, 192, 3), 128, np.uint8)
    for t in range(frames):
        for cell in (0, 1, 2, 3, 5, 6, 7, 8):
            top, left = divmod(cell, 3)
            top, left = top * 64, left * 64
            if poses[t]:
                video[t, top + 48:top + 60, left + 8:left + 56] = 230
            else:
                video[t, top + 8:top + 60, left + 26:left + 38] = 230
    if line:
        video[:, :, 62:66] = 255
        video[:, 62:66] = 255
    return video


def test_a_character_that_follows_the_driver_passes():
    poses = [t >= 4 for t in range(10)]
    assert seedance.check(grid(10, poses), grid(10, poses))["problems"] == []


def test_a_character_that_stands_still_fails():
    report = seedance.check(grid(10, [True] * 10), grid(10, [False] * 10))
    assert "doesn't follow" in report["problems"][0]


def test_grid_lines_fail():
    poses = [False] * 10
    report = seedance.check(grid(10, poses), grid(10, poses, line=True))
    assert any("grid lines" in problem for problem in report["problems"])


def test_the_prompt_ends_by_whether_the_motion_loops():
    assert seedance.prompt(True).endswith(seedance.LOOP + " Plain gray background.")
    assert seedance.prompt(False).endswith(seedance.ONCE + " Plain gray background.")


def test_mp4_round_trip_keeps_frames():
    frames = np.full((5, 64, 64, 3), 128, np.uint8)
    assert seedance.decode_mp4(seedance.encode_mp4(frames)).shape == (5, 64, 64, 3)
