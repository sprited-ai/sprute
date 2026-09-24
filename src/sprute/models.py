from pathlib import Path
from huggingface_hub import hf_hub_download

def download_model(
    repo_id: str,
    filename: str,
    *,
    revision: str,
    destination: Path,
) -> Path:
    cached = Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            revision=revision
        )
    ).resolve()
    destination = destination.expanduser().absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        if destination.resolve() == cached:
            return destination
        destination.unlink()
    elif destination.exists():
        raise FileExistsError(
            f"Model file already exists: {destination}"
        )
    destination.symlink_to(cached)
    return destination