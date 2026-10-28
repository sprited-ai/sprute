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


def test_keeps_the_frames_the_render_reports_before_picking_every_nth(tmp_path, monkeypatch):
    graph, _, _ = run_animate(tmp_path, monkeypatch)
    select = graph[graph["577"]["inputs"]["images"][0]]
    cut = graph[select["inputs"]["images"][0]]
    assert cut["class_type"] == "ImageFromBatch"
    assert cut["inputs"]["batch_index"] == 0
    render, output = cut["inputs"]["length"]
    assert (graph[render]["class_type"], output) == ("SpruteRenderDrivingVideo", 3)
    assert graph[cut["inputs"]["image"][0]]["class_type"] == "SpruteCellsToStrip"


def test_eight_directions_leave_the_layout_nodes_as_saved(tmp_path, monkeypatch):
    graph, _, _ = run_animate(tmp_path, monkeypatch)
    assert all("directions" not in graph[node]["inputs"] for node in animate_module.LAYOUT_NODES)


def test_four_directions_set_every_layout_node(tmp_path, monkeypatch):
    graph, _, _ = run_animate(tmp_path, monkeypatch, directions_drawn=4)
    assert [graph[node]["inputs"]["directions"] for node in animate_module.LAYOUT_NODES] == ["4"] * 4
    assert [graph[node]["class_type"] for node in animate_module.LAYOUT_NODES] == [
        "SpruteStripToGrid", "SpruteStripToGrid", "SpruteGridToCells", "SpruteCellsToStrip"]


def test_rejects_other_direction_counts(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="directions"):
        run_animate(tmp_path, monkeypatch, directions_drawn=6)


def _with_body(glb):
    """The GLB with a mesh entry added, as a rigged character would carry one."""
    import json, struct
    raw = glb.read_bytes()
    size = struct.unpack_from("<I", raw, 12)[0]
    doc = json.loads(raw[20:20 + size])
    doc["meshes"] = [{"primitives": []}]
    text = json.dumps(doc).encode()
    text += b" " * (-len(text) % 4)
    rest = raw[20 + size:]
    body = struct.pack("<II", len(text), 0x4E4F534A) + text + rest
    glb.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)
    return glb


def run_with(tmp_path, monkeypatch, glb, **options):
    runs = []
    monkeypatch.setattr(animate_module, "run_workflow", lambda graph, *, input_files, **_: runs.append((graph, input_files)) or {"577": b"RIFF"})
    path = animate_module.animate(_directions(tmp_path), str(glb), seed=1, out=tmp_path / "out", **options)
    (graph, files), = runs
    return graph, files, path


def test_a_glb_with_a_body_drives_through_the_rig_node_which_decides_who_performs(tmp_path, monkeypatch):
    wolf = tmp_path / "wolf.glb"
    shutil.copyfile(MOTIONS / "walk.glb", wolf)
    _with_body(wolf)
    graph, files, path = run_with(tmp_path, monkeypatch, wolf, clip="Gallop")
    driver = graph["4"]
    assert driver["class_type"] == "SpruteRenderRigVideo"
    assert (driver["inputs"]["animation"], driver["inputs"]["body"]) == ("Gallop", "auto")
    assert files[driver["inputs"]["rig"]] == wolf.resolve()
    assert "601" not in graph and "motion" not in driver["inputs"]
    assert path.name == "hero.gallop.webp"


def test_own_body_keeps_a_humanoid_glb_off_template_kun(tmp_path, monkeypatch):
    hero = tmp_path / "hero.glb"
    shutil.copyfile(MOTIONS / "walk.glb", hero)
    graph, _, _ = run_with(tmp_path, monkeypatch, _with_body(hero), own_body=True)
    assert graph["4"]["inputs"]["body"] == "own"


def test_own_body_needs_a_body(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="no mesh"):
        run_with(tmp_path, monkeypatch, MOTIONS / "walk.glb", own_body=True)


def test_a_motion_without_a_body_stays_on_template_kun_with_its_clip(tmp_path, monkeypatch):
    graph, _, path = run_with(tmp_path, monkeypatch, MOTIONS / "walk.glb", clip="walk")
    assert graph["4"]["class_type"] == "SpruteRenderDrivingVideo"
    assert graph["601"]["inputs"]["animation"] == "walk"
    assert path.name == "hero.walk.webp"


def _directions(tmp_path):
    directions = tmp_path / "hero.directions.png"
    Image.new("RGBA", (128, 16), (0, 0, 0, 0)).save(directions)
    return directions


def run_checked(tmp_path, monkeypatch, verdicts, attempts):
    """animate_checked with animate and check replaced: each attempt's verdict comes from `verdicts`."""
    import json
    from sprute import check as check_module
    directions = tmp_path / "hero.directions.png"
    Image.new("RGBA", (128, 16)).save(directions)
    seeds = []

    def animate(_directions, motion, *, seed, out, **_):
        seeds.append(seed)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"hero.{motion}.webp"
        path.write_bytes(str(seed).encode())
        return path

    monkeypatch.setattr(animate_module, "animate", animate)
    monkeypatch.setattr(check_module, "check", lambda *_, **__: {"verdict": verdicts[len(seeds) - 1]})
    path = animate_module.animate_checked(directions, "walk", attempts=attempts, seed=10, out=tmp_path / "out")
    return path, seeds, json.loads(path.with_name("hero.walk.check.json").read_text())


GOOD = {"SE": {"pass": True, "reasons": []}, "NE": {"pass": True, "reasons": []}}
ONE_BAD = {"SE": {"pass": True, "reasons": []}, "NE": {"pass": False, "reasons": ["turned around"]}}
TWO_BAD = {"SE": {"pass": False, "reasons": ["fades"]}, "NE": {"pass": False, "reasons": ["melts"]}}


def test_checked_animation_retries_with_the_next_seed_until_every_direction_passes(tmp_path, monkeypatch):
    path, seeds, report = run_checked(tmp_path, monkeypatch, [ONE_BAD, GOOD, GOOD], attempts=3)
    assert seeds == [10, 11]
    assert path.read_bytes() == b"11"
    assert (report["seed"], report["pass"]) == (11, True)
    assert [a["failing"] for a in report["attempts"]] == [{"NE": ["turned around"]}, {}]


def test_checked_animation_keeps_the_attempt_with_fewest_failures(tmp_path, monkeypatch):
    path, seeds, report = run_checked(tmp_path, monkeypatch, [TWO_BAD, ONE_BAD, TWO_BAD], attempts=3)
    assert seeds == [10, 11, 12]
    assert path.read_bytes() == b"11"
    assert (report["seed"], report["pass"]) == (11, False)
    assert not any(p.name.startswith(".attempts-") for p in path.parent.iterdir())
