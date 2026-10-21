from io import BytesIO

import pytest
from PIL import Image

from sprute import animate as animate_module


def write_inputs(tmp_path):
    directions = tmp_path / "hero.directions.png"
    Image.new("RGBA", (128, 16), (0, 0, 0, 0)).save(directions)
    # Frames differ so the encoder keeps all five.
    frames = [Image.new("RGBA", (128, 16), (0, 0, 0, 0)) for _ in range(5)]
    for i, frame in enumerate(frames):
        frame.putpixel((i, 0), (255, 255, 255, 255))
    video = BytesIO()
    frames[0].save(video, format="WEBP", save_all=True, append_images=frames[1:], lossless=True)
    driving = tmp_path / "wave.webp"
    driving.write_bytes(video.getvalue())
    return directions, driving


def run_animate(tmp_path, monkeypatch, **options):
    """Animate with ComfyUI replaced, returning the graph that would have run."""
    directions, driving = write_inputs(tmp_path)
    graphs = []

    def run_workflow(graph, **_):
        graphs.append(graph)
        return {"577": b"RIFF"}

    monkeypatch.setattr(animate_module, "run_workflow", run_workflow)
    animate_module.animate(directions, str(driving), seed=1, out=tmp_path / "out", **options)
    return graphs[0]


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
    graph = run_animate(tmp_path, monkeypatch)
    assert saved_frames(graph) == 2


def test_keeps_every_nth_frame(tmp_path, monkeypatch):
    graph = run_animate(tmp_path, monkeypatch, every=3)
    assert saved_frames(graph) == 3


def test_saved_fps_divides_by_every(tmp_path, monkeypatch):
    graph = run_animate(tmp_path, monkeypatch, every=3)
    assert saved_fps_expression(graph) == "24 / a"


@pytest.mark.parametrize("every", [0, -1, 1.5, True])
def test_rejects_every_that_is_not_a_positive_integer(tmp_path, monkeypatch, every):
    with pytest.raises(ValueError, match="every"):
        run_animate(tmp_path, monkeypatch, every=every)
