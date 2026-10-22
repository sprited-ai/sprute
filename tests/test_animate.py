import shutil
from pathlib import Path

import pytest
from PIL import Image

from sprute import animate as animate_module
from sprute import motion as motion_module
from sprute.comfy import input_name

MOTIONS = Path(__file__).resolve().parents[1] / "motions"


def run_animate(tmp_path, monkeypatch, motion="walk.glb", **options):
    """Animate with ComfyUI replaced. Returns the graph that would have run, the files it was given, and the GLB."""
    directions = tmp_path / "hero.directions.png"
    Image.new("RGBA", (128, 16), (0, 0, 0, 0)).save(directions)
    # A copy, so anything written beside the motion lands in tmp_path.
    glb = tmp_path / Path(motion).name
    shutil.copyfile(MOTIONS / motion, glb)
    runs = []

    def run_workflow(graph, *, input_files, **_):
        runs.append((graph, input_files))
        return {"577": b"RIFF"}

    def render_separately(*_, **__):
        raise AssertionError("the GLB is rendered inside the animate graph")

    monkeypatch.setattr(animate_module, "run_workflow", run_workflow)
    monkeypatch.setattr(motion_module, "run_workflow", render_separately)
    animate_module.animate(directions, str(glb), seed=1, out=tmp_path / "out", **options)
    (graph, files), = runs
    return graph, files, glb


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


def driving_video(graph):
    """The node the eight-direction strip and its mask come from."""
    strip, mask = graph["583"]["inputs"]["image"], graph["583"]["inputs"]["mask"]
    assert (strip, mask) == ([strip[0], 0], [strip[0], 1])
    return graph[strip[0]]


def test_keeps_every_second_frame_by_default(tmp_path, monkeypatch):
    graph, _, _ = run_animate(tmp_path, monkeypatch)
    assert saved_frames(graph) == 2


def test_keeps_every_nth_frame(tmp_path, monkeypatch):
    graph, _, _ = run_animate(tmp_path, monkeypatch, every=3)
    assert saved_frames(graph) == 3


def test_saved_fps_divides_by_every(tmp_path, monkeypatch):
    graph, _, _ = run_animate(tmp_path, monkeypatch, every=3)
    assert saved_fps_expression(graph) == "24 / a"


@pytest.mark.parametrize("every", [0, -1, 1.5, True])
def test_rejects_every_that_is_not_a_positive_integer(tmp_path, monkeypatch, every):
    with pytest.raises(ValueError, match="every"):
        run_animate(tmp_path, monkeypatch, every=every)


def test_renders_the_motion_inside_the_animate_graph(tmp_path, monkeypatch):
    graph, _, _ = run_animate(tmp_path, monkeypatch)
    render = driving_video(graph)
    assert render["class_type"] == "SpruteRenderDrivingVideo"
    assert graph[render["inputs"]["motion"][0]]["class_type"] == "SpruteLoadMotion"


def test_hands_comfyui_the_glb_by_its_content(tmp_path, monkeypatch):
    graph, files, glb = run_animate(tmp_path, monkeypatch)
    load = graph[driving_video(graph)["inputs"]["motion"][0]]
    assert load["inputs"]["motion"] == input_name(glb)
    assert files[input_name(glb)] == glb


def test_renders_cells_measured_from_the_directions_image(tmp_path, monkeypatch):
    # In the graph, so ComfyUI alone gets the size right too: the strip is eight cells wide.
    graph, _, _ = run_animate(tmp_path, monkeypatch)
    inputs = driving_video(graph)["inputs"]
    width = graph[inputs["cell_width"][0]]
    assert width["class_type"] == "ComfyMathExpression"
    assert (width["inputs"]["expression"], inputs["cell_width"][1]) == ("a / 8", 1)
    size = graph[inputs["cell_height"][0]]
    assert size["class_type"] == "GetImageSize"
    assert size["inputs"]["image"] == ["3", 0]
    assert (width["inputs"]["values.a"], inputs["cell_height"]) == ([inputs["cell_height"][0], 0], [inputs["cell_height"][0], 1])


def test_leaves_no_rendered_file_beside_the_motion(tmp_path, monkeypatch):
    _, _, glb = run_animate(tmp_path, monkeypatch)
    assert not glb.with_suffix(".cached.webp").exists()


def test_rejects_a_webp_driving_video(tmp_path):
    video = tmp_path / "wave.webp"
    Image.new("RGBA", (128, 16)).save(video)
    with pytest.raises(ValueError, match="GLB"):
        motion_module.find_motion(str(video))


def test_finds_a_bundled_motion_by_its_glb_even_beside_a_webp(tmp_path, monkeypatch):
    monkeypatch.setattr(motion_module, "MOTIONS", tmp_path)
    shutil.copyfile(MOTIONS / "walk.glb", tmp_path / "walk.glb")
    Image.new("RGBA", (128, 16)).save(tmp_path / "walk.webp")
    assert motion_module.find_motion("walk") == tmp_path / "walk.glb"


def test_snaps_the_motion_to_the_same_every_that_picks_frames(tmp_path, monkeypatch):
    graph, _, _ = run_animate(tmp_path, monkeypatch, every=4)
    select = graph[graph["577"]["inputs"]["images"][0]]
    assert driving_video(graph)["inputs"]["snap_to_multiple"] == select["inputs"]["select_every_nth"]


def test_can_leave_the_motion_unsnapped(tmp_path, monkeypatch):
    graph, _, _ = run_animate(tmp_path, monkeypatch, snap=False)
    assert driving_video(graph)["inputs"]["snap_to_multiple"] == 0
