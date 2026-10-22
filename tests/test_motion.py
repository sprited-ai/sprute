import shutil
from pathlib import Path

import pytest

from sprute import motion as motion_module

MOTIONS = Path(__file__).resolve().parents[1] / "motions"


def render_graph(tmp_path, monkeypatch, **options):
    """Render walk with ComfyUI replaced, returning the graph that would have run."""
    glb = tmp_path / "walk.glb"
    shutil.copyfile(MOTIONS / "walk.glb", glb)
    graphs = []

    def run_workflow(graph, **_):
        graphs.append(graph)
        return {"4": b"RIFF"}

    monkeypatch.setattr(motion_module, "run_workflow", run_workflow)
    motion_module.render_motion(glb, **options)
    return graphs[0]


def select(graph):
    node = graph[graph["4"]["inputs"]["images"][0]]
    assert node["class_type"] == "VHS_SelectEveryNthImage"
    return node


def every(graph):
    link = select(graph)["inputs"]["select_every_nth"]
    return graph[link[0]]["inputs"]["value"]


def test_keeps_every_second_frame_by_default(tmp_path, monkeypatch):
    assert every(render_graph(tmp_path, monkeypatch)) == 2


def test_keeps_every_nth_frame(tmp_path, monkeypatch):
    assert every(render_graph(tmp_path, monkeypatch, every=4)) == 4


def test_saves_at_24_fps_over_every(tmp_path, monkeypatch):
    graph = render_graph(tmp_path, monkeypatch, every=4)
    fps = graph[graph["4"]["inputs"]["fps"][0]]
    assert (fps["class_type"], fps["inputs"]["expression"]) == ("ComfyMathExpression", "24 / a")
    assert fps["inputs"]["values.a"] == select(graph)["inputs"]["select_every_nth"]


def test_snaps_the_motion_to_the_same_every(tmp_path, monkeypatch):
    graph = render_graph(tmp_path, monkeypatch, every=4)
    assert graph["2"]["inputs"]["snap_to_multiple"] == select(graph)["inputs"]["select_every_nth"]


def test_can_leave_the_motion_unsnapped(tmp_path, monkeypatch):
    graph = render_graph(tmp_path, monkeypatch, snap=False)
    assert graph["2"]["inputs"]["snap_to_multiple"] == 0


@pytest.mark.parametrize("value", [0, -1, 1.5, True])
def test_rejects_every_that_is_not_a_positive_integer(tmp_path, monkeypatch, value):
    with pytest.raises(ValueError, match="every"):
        render_graph(tmp_path, monkeypatch, every=value)
