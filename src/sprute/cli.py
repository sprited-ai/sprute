import typer
from pathlib import Path
from sprute.setup import setup as _setup
from sprute.events import Event
from sprute.generate import generate as _generate
from collections.abc import Callable
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.console import Console, Group, RenderableType
from time import monotonic
from collections import deque

app = typer.Typer(no_args_is_help=True)

console = Console(
    stderr=True,
    # force_interactive=False if verbose else None,
)

@app.callback()
def main():
    """Sprute — character sprite tools."""

@app.command()
def setup(
    models_dir: list[Path] = typer.Option(
        [], "--models-dir", file_okay=False,
        help="Model directories to search. Downloads go to the first; default: ./models. Can be repeated.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    reinstall: bool = typer.Option(
        False, "--reinstall", help="Reinstall ComfyUI and its dependencies."
    ),
):
    """Install and check Sprute dependencies."""
    run_with_panel(
        "Setup",
        lambda on_event: _setup(
            on_event=on_event, reinstall=reinstall, model_dirs=tuple(models_dir)
        ),
        verbose=verbose,
    )


def run_with_panel(
    title: str,
    action: Callable[[Callable[[Event], None]], object],
    *,
    verbose: bool = False,
) -> None:
    recent_logs: deque[str] = deque(maxlen=1)
    command_started_at = monotonic()
    started_at = command_started_at

    def duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes}m {seconds:02d}s"

    def event_duration(event: Event) -> str:
        nonlocal started_at
        if event.state == "started":
            started_at = monotonic()
        elif event.state == "completed":
            now = monotonic()
            elapsed = duration(now - started_at)
            started_at = now
            return elapsed
        return ""

    def print_log(message: str) -> None:
        console.print(
            Text.from_ansi(message),
            highlight=False,
        )
    if verbose or not console.is_interactive:
        def print_event(event: Event) -> None:
            if event.state == "progress":
                return
            if event.state == "log" and not verbose:
                return
            if event.state == "warning":
                console.print(Text(f"Warning: {event.message}", style="yellow"))
                return
            elapsed = event_duration(event)
            message = Text.from_ansi(event.message)
            if elapsed:
                message.append(f" · {elapsed}", style="dim")
            console.print(message, highlight=False)
        try:
            action(print_event)
        except Exception as error:
            console.print(str(error), markup=False, highlight=False)
            raise typer.Exit(code=1) from error
        console.print(f"{title} completed in {duration(monotonic() - command_started_at)}", style="dim")
        return

    completed: list[tuple[str, str]] = []
    warnings: list[str] = []
    current = ""
    failure: str | None = None
    spinner = Spinner("dots", style="cyan")
    def render () -> Panel:
        parts: list[RenderableType] = []
        for message, elapsed in completed:
            label = Text("✓ ", style="green")
            label.append(message, style="default")
            label.append(f" · {elapsed}", style="dim")
            parts.append(label)
        for message in warnings:
            parts.append(Text(f"⚠ {message}", style="yellow"))
        if failure is not None:
            error_text = Text(f"✗ {title} failed\n", style="red")
            error_text.append(failure, style="default")
            parts.append(error_text)
        elif current:
            elapsed = duration(monotonic() - started_at)
            label = Text(current)
            label.append(f" · {elapsed}", style="dim")
            spinner.update(text=label)
            parts.append(spinner)
            for message in recent_logs:
                parts.append(
                    Text(
                        f"  {message}",
                        style="dim",
                        no_wrap=True,
                        overflow="ellipsis",
                    )
                )
        return Panel(
            Group(*parts), 
            title=title,
            title_align="left",
        )        

    with Live(
        get_renderable=render, 
        console=console,
        refresh_per_second=4
    ) as live:
        def on_event(event: Event) -> None:
            nonlocal current
            if event.state == "warning":
                warnings.append(event.message)
                live.update(render())
                return
            if event.state == "log":
                if verbose:
                    print_log(event.message)
                message = Text.from_ansi(event.message).plain.strip()
                if message:
                    recent_logs.append(message)
                return
            if event.state == "started":
                event_duration(event)
                current = event.message
                recent_logs.clear()
            elif event.state == "progress":
                current = event.message
            else:
                completed.append((event.message, event_duration(event)))
                current = ""
            live.update(render())
        try:
            action(on_event)
        except Exception as error:
            current = ""
            failure = str(error)
            live.update(render(), refresh=True)
    if failure is not None:
        raise typer.Exit(code=1)
    console.print(f"{title} completed in {duration(monotonic() - command_started_at)}", style="dim")

@app.command()
def generate(
    prompt: str = "",
    seed: int = 42,
    out: Path = Path("outputs"),
    models_dir: list[Path] = typer.Option(
        [], "--models-dir", exists=True, file_okay=False,
        help="Model directories to search. Default: ./models. Can be repeated.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Generate a character from a text prompt."""
    run_with_panel(
        "Generate",
        lambda on_event: _generate(
            prompt, seed=seed, out=out,
            model_dirs=tuple(models_dir), on_event=on_event,
        ),
        verbose=verbose,
    )
