import typer
import shutil
import subprocess
import sys
from pathlib import Path
from sprute.setup import setup as _setup
from sprute.events import Event
from sprute.generate import generate as _generate
from sprute.turntable import turntable as _turntable
from sprute.config import model_directories
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
    models_directory: Path | None = typer.Option(
        None, "--models-directory", file_okay=False,
        help="Override the config models directory. Downloads go here.",
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
            on_event=on_event, reinstall=reinstall, model_dirs=model_directories(models_directory)
        ),
        verbose=verbose,
    )


def run_with_panel[T](
    title: str,
    action: Callable[[Callable[[Event], None]], T],
    *,
    verbose: bool = False,
    prompt: str | None = None,
) -> T:
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
        if prompt is not None:
            console.print(Text(f"Prompt: {prompt}"))
        def print_event(event: Event) -> None:
            if event.state == "image":
                show_sprite(Path(event.message))
                return
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
            result = action(print_event)
        except Exception as error:
            console.print(str(error), markup=False, highlight=False)
            raise typer.Exit(code=1) from error
        console.print(f"{title} completed in {duration(monotonic() - command_started_at)}", style="dim")
        return result

    completed: list[tuple[str, str]] = []
    warnings: list[str] = []
    current = ""
    failure: str | None = None
    spinner = Spinner("dots", style="cyan")
    def render () -> Panel:
        parts: list[RenderableType] = []
        if prompt is not None:
            label = Text("Prompt: ", style="dim")
            label.append(prompt, style="default")
            parts.extend([label, Text("")])
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

    def create_live() -> Live:
        return Live(
            get_renderable=render,
            console=console,
            refresh_per_second=4,
            transient=True,
        )

    live = create_live()
    live.start(refresh=True)
    try:
        def on_event(event: Event) -> None:
            nonlocal current, live
            if event.state == "image":
                # Clear and stop refresh before imgcat changes the cursor position.
                live.stop()
                try:
                    show_sprite(Path(event.message))
                finally:
                    # A fresh Live has no previous panel height to rewind over the image.
                    live = create_live()
                    live.start(refresh=True)
                return
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
            result = action(on_event)
        except Exception as error:
            current = ""
            failure = str(error)
            raise typer.Exit(code=1) from error
    finally:
        live.stop()
        console.print(render())
    console.print(f"{title} completed in {duration(monotonic() - command_started_at)}", style="dim")
    return result

@app.command()
def generate(
    prompt: str = "",
    name: str | None = typer.Option(None, help="Character name; numbered automatically when omitted."),
    seed: int | None = typer.Option(None, help="Random when omitted; specify to reproduce a run."),
    out: Path = Path("output"),
    batch: int = typer.Option(1, min=1, help="Number of characters to generate sequentially."),
    models_directory: Path | None = typer.Option(
        None, "--models-directory", exists=True, file_okay=False,
        help="Override the config models directory. Default: config or ./models.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    preview: bool = typer.Option(True, "--preview/--no-preview", help="Show the sprite with imgcat in an interactive terminal."),
):
    """Generate a character from a text prompt."""
    def generate_batch(on_event: Callable[[Event], None]) -> None:
        directories = model_directories(models_directory)
        for index in range(batch):
            character_name = (
                f"{name}-{index + 1:04d}" if name is not None and batch > 1 else name
            )
            character_seed = (seed + index) % (2**32) if seed is not None and batch > 1 else seed

            def report(event: Event) -> None:
                if batch > 1 and event.state == "started":
                    event = Event(
                        event.state,
                        event.message.replace("Generating character", f"Generating character {index + 1} of {batch}", 1),
                        event.timed,
                    )
                on_event(event)

            image = _generate(
                prompt, seed=character_seed, out=out, name=character_name,
                model_dirs=directories, on_event=report,
            )
            if preview:
                on_event(Event("image", str(image)))

    run_with_panel("Generate", generate_batch, verbose=verbose, prompt=prompt)


def show_sprite(image: Path) -> None:
    """Display while Live is stopped; never send image escapes into redirected output."""
    if not sys.stdout.isatty():
        return
    imgcat = shutil.which("imgcat")
    if imgcat is None:
        return
    try:
        subprocess.run(
            [imgcat, "-W", "320px", str(image)],
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        console.print(f"Image saved, but terminal preview failed: {error}", style="yellow", markup=False)



@app.command()
def turntable(
    image: Path = typer.Option(..., exists=True, dir_okay=False, help="Character reference image."),
    seed: int | None = typer.Option(None, help="Random when omitted; specify to reproduce a run."),
    out: Path = Path("output"),
    models_directory: Path | None = typer.Option(
        None, "--models-directory", exists=True, file_okay=False,
        help="Override the config models directory. Default: config or ./models.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    preview: bool = typer.Option(True, "--preview/--no-preview"),
):
    """Generate a turntable and extract eight directional views."""
    def run(on_event: Callable[[Event], None]) -> Path:
        strip = _turntable(
            image, seed=seed, out=out,
            model_dirs=model_directories(models_directory), on_event=on_event,
        )
        if preview:
            on_event(Event("image", str(strip)))
        return strip

    run_with_panel("Turntable", run, verbose=verbose)
