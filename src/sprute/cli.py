import typer
from pathlib import Path
from sprute.setup import setup as _setup
from sprute.setup import SetupEvent
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
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    reinstall: bool = typer.Option(
        False, "--reinstall", help="Reinstall ComfyUI and its dependencies."
    ),
):
    """Install and check Sprute dependencies."""
    recent_logs: deque[str] = deque(maxlen=1)
    started_at = monotonic()
    def print_log(message: str) -> None:
        console.print(
            Text.from_ansi(message),
            highlight=False,
        )
    if not console.is_interactive:
        def print_event(event: SetupEvent) -> None:
            if event.state == "log" and not verbose:
                return
            print_log(event.message)
        try:
            _setup(on_event=print_event, reinstall=reinstall)
        except Exception as error:
            console.print(str(error), markup=False, highlight=False)
            raise typer.Exit(code=1) from error
        return

    completed: list[str] = []
    current = ""
    failure: str | None = None
    spinner = Spinner("dots", style="cyan")
    def render () -> Panel:
        content = Text()
        for message in completed:
            if content.plain:
                content.append("\n")
            content.append("✓ ", style="green")
            content.append(message)
        parts: list[RenderableType] = [content] if completed else []
        if failure is not None:
            error_text = Text("✗ Setup failed\n", style="red")
            error_text.append(failure, style="default")
            parts.append(error_text)
        elif current:
            elapsed = int(monotonic() - started_at)
            minutes, seconds = divmod(elapsed, 60)
            spinner.update(
                text=Text(f"{current} · {minutes:02d}:{seconds:02d}")
            )
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
            title="Setup", 
            title_align="left",
        )        

    with Live(
        get_renderable=render, 
        console=console,
        refresh_per_second=4
    ) as live:
        def on_event(event: SetupEvent) -> None:
            nonlocal current
            if event.state == "log":
                if verbose:
                    print_log(event.message)
                message = Text.from_ansi(event.message).plain.strip()
                if message:
                    recent_logs.append(message)
                return
            if event.state == "started":
                current = event.message
                recent_logs.clear()
            else:
                completed.append(event.message)
                current = ""
            live.update(render())
        try:
            _setup(on_event=on_event, reinstall=reinstall)
        except Exception as error:
            current = ""
            failure = str(error)
            live.update(render(), refresh=True)
    if failure is not None:
        raise typer.Exit(code=1)

@app.command()
def generate(
    prompt: str = "", 
    seed: int = 42, 
    out: Path = Path("outputs"),
):
    """Generate a character from a text prompt."""
    # TODO: Implement this
    print(f"Prompt: {prompt}")
    print(f"Seed: {seed}")
    print(f"Output: {out}")
