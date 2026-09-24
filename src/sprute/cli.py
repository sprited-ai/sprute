import typer
from pathlib import Path
from sprute.setup import setup as _setup
from sprute.setup import SetupEvent
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.console import Console, Group, RenderableType

app = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)

@app.callback()
def main():
    """Sprute — character sprite tools."""

@app.command()
def setup(workspace: Path = Path("workspace")):
    """Prepare the Sprute workspace"""
    location = workspace
    completed: list[str] = []
    current = ""
    failure: str | None = None
    def render () -> Panel:
        content = Text(f"Workspace: {location}\n")
        for message in completed:
            content.append("\n✓ ", style="green")
            content.append(message)
        parts: list[RenderableType] = [content]
        if failure is not None:
            error_text = Text("✗ Setup failed\n", style="red")
            error_text.append(failure, style="default")
            parts.append(error_text)
        elif current:
            parts.append(
                Spinner("dots", text=Text(current), style="cyan")
            )
        return Panel(
            Group(*parts), 
            title="Setup", 
            title_align="left",
        )        

    with Live(
        render(), 
        console=console,
        refresh_per_second=10
    ) as live:
        def on_event(event: SetupEvent) -> None:
            nonlocal current
            if event.state == "started":
                current = event.message
            else:
                completed.append(event.message)
                current = ""
            live.update(render())
        try:
            location = workspace.expanduser().resolve()
            live.update(render())
            _setup(workspace, on_event=on_event)
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