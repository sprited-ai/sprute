from typer.testing import CliRunner

from sprute import cli


def options(monkeypatch, command, *arguments):
    """Run a command up to its work, and return the options it works with."""
    calls = []
    monkeypatch.setattr(cli, "character_file", lambda *_: "hero.directions.png")
    monkeypatch.setattr(cli, "set_models_directory", lambda *_: None)
    monkeypatch.setattr(cli, "require_setup", lambda *_, **__: None)
    monkeypatch.setattr(cli, "_animate", lambda *_, **options: calls.append(options) or "hero.walk.webp")
    monkeypatch.setattr(cli, "_render_motion", lambda *_, **options: calls.append(options) or b"")
    monkeypatch.setattr(cli, "run_with_panel", lambda _title, run, **__: run(lambda _event: None))
    arguments = {"animate": ["animate", "character", "--character", "hero"], "render": ["render", "motion"]}[command] + [
        "--motion", "walk", "--no-preview", *arguments]
    result = CliRunner().invoke(cli.app, arguments)
    assert result.exit_code == 0, result.output
    return calls[0]


def test_animate_keeps_every_second_frame_and_snaps_by_default(monkeypatch):
    chosen = options(monkeypatch, "animate")
    assert (chosen["every"], chosen["snap"]) == (2, True)


def test_animate_can_leave_the_motion_unsnapped(monkeypatch):
    assert options(monkeypatch, "animate", "--no-snap")["snap"] is False


def test_render_keeps_every_second_frame_and_snaps_by_default(monkeypatch):
    chosen = options(monkeypatch, "render")
    assert (chosen["every"], chosen["snap"]) == (2, True)


def test_render_takes_the_same_options_as_animate(monkeypatch):
    chosen = options(monkeypatch, "render", "--every", "4", "--no-snap")
    assert (chosen["every"], chosen["snap"]) == (4, False)


def test_animate_draws_eight_directions_by_default(monkeypatch):
    assert options(monkeypatch, "animate")["directions_drawn"] == 8


def test_animate_can_draw_only_the_diagonals(monkeypatch):
    assert options(monkeypatch, "animate", "--directions", "4")["directions_drawn"] == 4
