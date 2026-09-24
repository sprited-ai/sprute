import json
from pathlib import Path
from collections.abc import Sequence


def model_directories(overrides: Sequence[Path] = ()) -> tuple[Path, ...]:
    """Resolve CLI overrides, working-directory config, or ./models."""
    if overrides:
        return tuple(path.expanduser().resolve() for path in overrides)

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
