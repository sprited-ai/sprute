"""Restore bundled weight parts locally, without network access."""
import hashlib
import json
import os
from pathlib import Path


def assemble_weights(models: Path) -> None:
    manifest = models / ".parts" / "manifest.json"
    if not manifest.is_file():
        return
    for entry in json.loads(manifest.read_text()):
        target = models / entry["destination"]
        if target.is_file() and target.stat().st_size == entry["size"]:
            continue
        print(f"Restoring bundled {target.name}", flush=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        digest = hashlib.sha256()
        try:
            with temporary.open("wb") as output:
                for name in entry["parts"]:
                    with (manifest.parent / name).open("rb") as source:
                        while chunk := source.read(8 * 1024 * 1024):
                            digest.update(chunk)
                            output.write(chunk)
            if temporary.stat().st_size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                raise RuntimeError(f"Bundled weight integrity check failed: {target.name}")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    import sys
    assemble_weights(Path(sys.argv[1]))
