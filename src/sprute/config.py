import json
from pathlib import Path


def model_directories(override: Path | None = None) -> tuple[Path, ...]:
    """Resolve the CLI override, working-directory config, or ./models."""
    if override is not None:
        return (override.expanduser().resolve(),)

    config = Path.cwd() / "sprute.config.json"
    if not config.exists():
        return (Path("models").resolve(),)

    try:
        settings = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read {config}: {error}") from error
    if not isinstance(settings, dict):
        raise ValueError(f"{config}: expected a JSON object")

    paths = settings.get("models_dirs", ["./models"])
    if not isinstance(paths, list) or not paths or any(
        not isinstance(path, str) or not path.strip() for path in paths
    ):
        raise ValueError(f"{config}: models_dirs must be a non-empty list of paths")

    return tuple((config.parent / Path(path).expanduser()).resolve() for path in paths)
