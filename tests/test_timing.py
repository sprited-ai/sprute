from pathlib import Path

import pytest

from sprute.timing import glb_cycle, plan

MOTIONS = Path(__file__).resolve().parents[1] / "motions"


def test_a_loop_that_fits_renders_at_24_fps():
    walk = plan(32 / 24, loop=True, every=2)
    assert (walk.cycle, walk.fps, walk.scale) == (32, pytest.approx(24), pytest.approx(1))


def test_a_loop_snaps_its_cycle_to_a_multiple_of_every():
    # jog-fwd: 0.933 s is 22.4 frames at 24 fps.
    assert plan(0.9333, loop=True, every=4).cycle == 24


def test_a_snapped_loop_renders_its_whole_cycle_in_those_frames():
    jog = plan(0.9333, loop=True, every=4)
    assert jog.cycle / jog.fps == pytest.approx(0.9333)


def test_a_snapped_loop_reports_how_much_longer_it_plays():
    # jog-fwd plays 24 frames at 24 fps: 1.0 s instead of 0.933 s.
    assert plan(0.9333, loop=True, every=4).scale == pytest.approx(1 / 0.9333)


def test_a_snapped_loop_reports_how_much_shorter_it_plays():
    # climb-left: 20.8 frames snapped to 20.
    assert plan(0.8667, loop=True, every=2).scale == pytest.approx(20 / (0.8667 * 24))


@pytest.mark.parametrize("every", [1, 2, 3, 4])
@pytest.mark.parametrize("seconds", [0.05, 0.2667, 0.8667, 0.9333, 1.3333, 2.3, 4.6])
def test_every_loop_cycle_is_a_multiple_of_every(seconds, every):
    assert plan(seconds, loop=True, every=every).cycle % every == 0


def test_a_short_loop_keeps_at_least_one_frame_after_every():
    assert plan(0.05, loop=True, every=4).cycle == 4


def test_a_clip_that_does_not_loop_renders_at_24_fps():
    punch = plan(0.8667, loop=False, every=2)
    assert (punch.fps, punch.scale) == (24.0, 1.0)


def test_reads_the_cycle_of_a_sprute_motion():
    seconds, loop = glb_cycle(MOTIONS / "walk.glb")
    assert (seconds, loop) == (pytest.approx(32 / 24), True)


def test_reads_the_cycle_of_a_quaternius_motion():
    seconds, loop = glb_cycle(MOTIONS / "quaternius" / "jog-fwd.glb")
    assert (seconds, loop) == (pytest.approx(28 / 30), True)


def test_reads_a_motion_that_does_not_loop():
    assert glb_cycle(MOTIONS / "quaternius" / "punch-jab.glb")[1] is False
