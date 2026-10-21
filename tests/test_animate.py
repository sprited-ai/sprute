import shutil
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from sprute import animate as animate_module
from sprute import motion as motion_module

MOTIONS = Path(__file__).resolve().parents[1] / "motions"


def driving_video(frames=5):
    # Frames differ so the encoder keeps them all.
    images = [Image.new("RGBA", (128, 16), (0, 0, 0, 0)) for _ in range(frames)]
    for i, image in enumerate(images):
        image.putpixel((i % 128, 0), (255, 255, 255, 255))
    video = BytesIO()
    images[0].save(video, format="WEBP", save_all=True, append_images=images[1:], lossless=True)
    return video.getvalue()


def run_animate(tmp_path, monkeypatch, motion=None, **options):
    """Animate with ComfyUI replaced. Returns the animate graph and the render graph, if a GLB was rendered."""
    directions = tmp_path / "hero.directions.png"
    Image.new("RGBA", (128, 16), (0, 0, 0, 0)).save(directions)
    if motion is None:
        driving = tmp_path / "wave.webp"
        driving.write_bytes(driving_video())
    else:
        # A copy, so the render cache lands in tmp_path rather than the repository.
        driving = tmp_path / Path(motion).name
        shutil.copyfile(MOTIONS / motion, driving)
    graphs = {}

    def animate_workflow(graph, **_):
        graphs["animate"] = graph
        return {"577": b"RIFF"}

    def render_workflow(graph, **_):
        graphs["render"] = graph
        return {"4": driving_video(81)}

    monkeypatch.setattr(animate_module, "run_workflow", animate_workflow)
    monkeypatch.setattr(motion_module, "run_workflow", render_workflow)
    animate_module.animate(directions, str(driving), seed=1, out=tmp_path / "out", **options)
    return graphs["animate"], graphs.get("render")


def time_scale(graph):
    """Recorded, not used: how much longer the saved animation plays than its motion."""
    scale, = [node for node in graph.values() if node.get("_meta", {}).get("title") == "Time Scale"]
    return scale["inputs"]["value"]


def saved_frames(graph):
    """Follow the saved animation's images back to the node that picks frames."""
    node = graph[graph["577"]["inputs"]["images"][0]]
    assert node["class_type"] == "VHS_SelectEveryNthImage"
    every = node["inputs"]["select_every_nth"]
    return graph[every[0]]["inputs"]["value"] if isinstance(every, list) else every


def saved_fps_expression(graph):
    """The saved fps as an expression of the same `every` value that picks frames."""
    fps = graph["577"]["inputs"]["fps"]
    node = graph[fps[0]]
    assert node["class_type"] == "ComfyMathExpression"
    select = graph[graph["577"]["inputs"]["images"][0]]
    assert node["inputs"]["values.a"] == select["inputs"]["select_every_nth"]
    return node["inputs"]["expression"]


def test_keeps_every_second_frame_by_default(tmp_path, monkeypatch):
    graph, _ = run_animate(tmp_path, monkeypatch)
    assert saved_frames(graph) == 2


def test_keeps_every_nth_frame(tmp_path, monkeypatch):
    graph, _ = run_animate(tmp_path, monkeypatch, every=3)
    assert saved_frames(graph) == 3


def test_saved_fps_divides_by_every(tmp_path, monkeypatch):
    graph, _ = run_animate(tmp_path, monkeypatch, every=3)
    assert saved_fps_expression(graph) == "24 / a"


@pytest.mark.parametrize("every", [0, -1, 1.5, True])
def test_rejects_every_that_is_not_a_positive_integer(tmp_path, monkeypatch, every):
    with pytest.raises(ValueError, match="every"):
        run_animate(tmp_path, monkeypatch, every=every)


def test_a_looping_glb_that_fits_renders_at_24_fps(tmp_path, monkeypatch):
    graph, render = run_animate(tmp_path, monkeypatch, "walk.glb")
    assert (render["2"]["inputs"]["frames"], render["2"]["inputs"]["fps"]) == (81, pytest.approx(24))
    assert time_scale(graph) == pytest.approx(1)


def test_a_snapped_loop_renders_at_its_planned_frame_rate(tmp_path, monkeypatch):
    # jog-fwd: 22.4 frames at 24 fps becomes 24 frames, rendered at 25.7 fps, with every 4.
    _, render = run_animate(tmp_path, monkeypatch, "quaternius/jog-fwd.glb", every=4)
    assert (render["2"]["inputs"]["frames"], render["2"]["inputs"]["fps"]) == (81, pytest.approx(24 / (28 / 30)))


def test_records_the_time_scale_in_the_saved_workflow(tmp_path, monkeypatch):
    # jog-fwd plays 24 frames at 24 fps: 1.0 s instead of 0.933 s.
    graph, _ = run_animate(tmp_path, monkeypatch, "quaternius/jog-fwd.glb", every=4)
    assert time_scale(graph) == pytest.approx(30 / 28)


def test_a_glb_that_does_not_loop_renders_at_24_fps(tmp_path, monkeypatch):
    graph, render = run_animate(tmp_path, monkeypatch, "quaternius/punch-jab.glb")
    assert render["2"]["inputs"]["fps"] == 24.0
    assert time_scale(graph) == 1.0


def test_a_driving_video_is_not_rescaled(tmp_path, monkeypatch):
    graph, _ = run_animate(tmp_path, monkeypatch)
    assert time_scale(graph) == 1.0


def test_snapping_a_loop_leaves_the_inference_scale_alone(tmp_path, monkeypatch):
    graph, _ = run_animate(tmp_path, monkeypatch, "quaternius/jog-fwd.glb", every=4)
    assert graph["587"]["inputs"]["value"] == 1.0
