from typer.testing import CliRunner

from sprute import cli


def animate_options(monkeypatch, *arguments):
    """Run `sprute animate character` up to animating, and return the options it animates with."""
    calls = []
    monkeypatch.setattr(cli, "character_file", lambda *_: "hero.directions.png")
    monkeypatch.setattr(cli, "set_models_directory", lambda *_: None)
    monkeypatch.setattr(cli, "require_setup", lambda *_, **__: None)
    monkeypatch.setattr(cli, "_animate", lambda *_, **options: calls.append(options) or "hero.walk.webp")
    monkeypatch.setattr(cli, "run_with_panel", lambda _title, run, **__: run(lambda _event: None))
    result = CliRunner().invoke(cli.app, ["animate", "character", "--character", "hero", "--motion", "walk", "--no-preview", *arguments])
    assert result.exit_code == 0, result.output
    return calls[0]


def test_snaps_loops_by_default(monkeypatch):
    assert animate_options(monkeypatch)["snap_to_multiple"] is True


def test_can_leave_loops_unsnapped(monkeypatch):
    assert animate_options(monkeypatch, "--no-snap-to-multiple")["snap_to_multiple"] is False
