import pytest
from PIL import Image

from sprute import turntable as turntable_module


def run_turntable(tmp_path, monkeypatch, **options):
    """Turntable with ComfyUI replaced. Returns the graph that would have run."""
    image = tmp_path / "hero.character.png"
    Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(image)
    runs = []

    def run_workflow(graph, **_):
        runs.append(graph)
        return {node: b"RIFF" for node in ("17", "28", "34")}

    monkeypatch.setattr(turntable_module, "run_workflow", run_workflow)
    turntable_module.turntable(image, seed=1, out=tmp_path / "out", **options)
    graph, = runs
    return graph


def cell_size(graph):
    return graph["37"]["inputs"]["value"], graph["38"]["inputs"]["value"]


def test_cells_are_256_by_default(tmp_path, monkeypatch):
    assert cell_size(run_turntable(tmp_path, monkeypatch)) == (256, 256)


def test_cells_can_be_larger(tmp_path, monkeypatch):
    graph = run_turntable(tmp_path, monkeypatch, cell=512)
    assert cell_size(graph) == (512, 512)
    assert graph["8"]["inputs"]["width"] == ["37", 0] and graph["8"]["inputs"]["height"] == ["38", 0]


@pytest.mark.parametrize("cell", [100, 300, 2048, True])
def test_rejects_cells_that_are_not_multiples_of_32_in_range(tmp_path, monkeypatch, cell):
    with pytest.raises(ValueError, match="cell"):
        run_turntable(tmp_path, monkeypatch, cell=cell)
