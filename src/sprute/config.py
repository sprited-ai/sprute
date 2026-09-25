import json
from pathlib import Path


_models_directory: Path | None = None


def set_models_directory(path: Path | None) -> None:
    """Override the models directory for this process, e.g. from --models-directory."""
    global _models_directory
    _models_directory = None if path is None else path.expanduser().resolve()


def get_models_directory() -> Path:
    """The override, else working-directory config, else ./models."""
    if _models_directory is not None:
        return _models_directory

    config = Path.cwd() / "sprute.config.json"
    if not config.exists():
        return Path("models").resolve()

    try:
        settings = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read {config}: {error}") from error
    if not isinstance(settings, dict):
        raise ValueError(f"{config}: expected a JSON object")

    if "models_dirs" in settings:
        raise ValueError(f"{config}: models_dirs was replaced by models_directory (a single path)")
    path = settings.get("models_directory", "./models")
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"{config}: models_directory must be a path")

    return (config.parent / Path(path).expanduser()).resolve()
