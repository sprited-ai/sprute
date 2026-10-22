import pytest

from conftest import node_module

snap = node_module("snap")


def motion(frames, fps, loop=True):
    """A motion as Load Motion gives it: name, fps, loop, rotations, hips."""
    return "test", fps, loop, {}, [None] * frames


def test_a_loop_that_fits_renders_at_the_requested_fps():
    # walk: 32 frames at 24 fps.
    assert snap.snapped_fps(motion(32, 24.0), 24.0, every=2) == pytest.approx(24)


def test_a_loop_snaps_its_cycle_to_a_multiple_of_every():
    # jog-fwd: 0.933 s is 22.4 frames at 24 fps; with every 4 it becomes 24.
    assert snap.cycle_frames(28 / 30, 24.0, every=4) == 24


def test_a_snapped_loop_renders_its_whole_cycle_in_those_frames():
    jog = motion(28, 30.0)
    assert snap.snapped_fps(jog, 24.0, every=4) == pytest.approx(24 / (28 / 30))


@pytest.mark.parametrize("every", [1, 2, 3, 4])
@pytest.mark.parametrize("seconds", [0.05, 0.2667, 0.8667, 0.9333, 1.3333, 2.3, 4.6])
def test_every_loop_cycle_is_a_multiple_of_every(seconds, every):
    assert snap.cycle_frames(seconds, 24.0, every) % every == 0


def test_a_short_loop_keeps_at_least_one_frame_after_every():
    assert snap.cycle_frames(0.05, 24.0, every=4) == 4


def test_a_clip_that_does_not_loop_ends_on_a_kept_frame():
    # punch-jab: 27 keys at 30 fps span 0.867 s, 20.8 frames at 24 fps; its last key is its last pose.
    punch = motion(27, 30.0, loop=False)
    assert snap.snapped_fps(punch, 24.0, every=2) == pytest.approx(20 / (26 / 30))


def test_a_single_pose_keeps_the_requested_fps():
    assert (snap.snapped_fps(motion(1, 30.0, loop=False), 24.0, every=2),
            snap.time_scale(motion(1, 30.0, loop=False), 24.0, every=2)) == (24.0, 1.0)


def test_a_snapped_loop_reports_how_much_longer_it_plays():
    # jog-fwd plays 24 frames at 24 fps: 1.0 s instead of 0.933 s.
    assert snap.time_scale(motion(28, 30.0), 24.0, every=4) == pytest.approx(30 / 28)


def test_a_snapped_loop_reports_how_much_shorter_it_plays():
    # climb-left: 20.8 frames snapped to 20.
    assert snap.time_scale(motion(26, 30.0), 24.0, every=2) == pytest.approx(20 / 20.8)


def test_a_loop_that_fits_keeps_its_time():
    assert snap.time_scale(motion(32, 24.0), 24.0, every=2) == pytest.approx(1)


def test_a_snapped_clip_reports_how_much_shorter_it_plays():
    assert snap.time_scale(motion(27, 30.0, loop=False), 24.0, every=2) == pytest.approx(20 / 20.8)


def test_a_multiple_of_zero_leaves_the_motion_as_it_is():
    jog = motion(28, 30.0)
    assert (snap.snapped_fps(jog, 24.0, every=0), snap.time_scale(jog, 24.0, every=0)) == (24.0, 1.0)


def test_keeps_one_cycle_of_a_snapped_loop():
    # walk: 32 frames.
    assert snap.keep_frames(motion(32, 24.0), 24.0, every=2, frames=81) == 32


def test_keeps_one_snapped_cycle():
    # jog-fwd: 22.4 frames, snapped to 24 with every 4.
    assert snap.keep_frames(motion(28, 30.0), 24.0, every=4, frames=81) == 24


def test_keeps_a_clip_up_to_and_including_its_last_pose():
    # punch-jab: 20.8 frames snapped to 20, and frame 20 is its last pose.
    assert snap.keep_frames(motion(27, 30.0, loop=False), 24.0, every=2, frames=81) == 21


def test_keeps_every_frame_of_an_unsnapped_clip():
    # Its last pose falls between frames.
    assert snap.keep_frames(motion(27, 30.0, loop=False), 24.0, every=0, frames=81) == 81


def test_keeps_every_frame_when_a_clip_does_not_fit():
    # 5 s is 120 frames.
    assert snap.keep_frames(motion(151, 30.0, loop=False), 24.0, every=2, frames=81) == 81


def test_keeps_every_frame_of_an_unsnapped_loop():
    # Its cycle isn't a whole number of frames, so a cut would wrap by a short step.
    assert snap.keep_frames(motion(28, 30.0), 24.0, every=0, frames=81) == 81


def test_keeps_every_frame_when_a_cycle_does_not_fit():
    # idle-lookaround: 4.6 s is 110 frames.
    assert snap.keep_frames(motion(138, 30.0), 24.0, every=2, frames=81) == 81
