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


def test_a_clip_that_does_not_loop_renders_at_the_requested_fps():
    punch = motion(26, 30.0, loop=False)
    assert snap.snapped_fps(punch, 24.0, every=4) == 24.0


def test_a_snapped_loop_reports_how_much_longer_it_plays():
    # jog-fwd plays 24 frames at 24 fps: 1.0 s instead of 0.933 s.
    assert snap.time_scale(motion(28, 30.0), 24.0, every=4) == pytest.approx(30 / 28)


def test_a_snapped_loop_reports_how_much_shorter_it_plays():
    # climb-left: 20.8 frames snapped to 20.
    assert snap.time_scale(motion(26, 30.0), 24.0, every=2) == pytest.approx(20 / 20.8)


def test_a_loop_that_fits_keeps_its_time():
    assert snap.time_scale(motion(32, 24.0), 24.0, every=2) == pytest.approx(1)


def test_a_clip_that_does_not_loop_keeps_its_time():
    assert snap.time_scale(motion(26, 30.0, loop=False), 24.0, every=4) == 1.0
