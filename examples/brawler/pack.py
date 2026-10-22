"""Pack a sprute character's animation strips into atlases the brawler can load.

A sprute animation is a strip: eight direction cells side by side (S, SE, E,
NE, N, NW, W, SW), one strip per frame. The game wants one image per motion
with a row per direction and a column per frame, so this reshapes each strip,
drops frames down to --fps, and scales the cells down.

    python examples/brawler/pack.py output/quaternius-0001-20261009 --name 0001
"""

import argparse
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
LIBRARY = HERE.parents[1] / "motions" / "quaternius" / "library.json"
DIRECTIONS = 8

# Game motion -> sprute motion. Every character the game loads has these.
MOTIONS = {
    "idle": "idle",
    "walk": "walk",
    "run": "jog-fwd",
    "punch": "punch-jab",
    "kick": "kick",
    "hit": "hit-chest",
    "death": "death01",
    "win": "celebration",
}


def loops() -> dict[str, bool]:
    library = json.loads(LIBRARY.read_text())
    return {Path(m["file"]).stem: m["loop"] for m in library["motions"]}


def frames(strip: Image.Image, fps: float) -> list[Image.Image]:
    """Frames of the strip resampled to fps, by the WebP's own frame durations."""
    kept, clock, due = [], 0.0, 0.0
    for index in range(strip.n_frames):
        strip.seek(index)
        if clock >= due - 1e-6:
            kept.append(strip.convert("RGBA"))
            due += 1000 / fps
        clock += strip.info.get("duration") or 1000 / 24
    return kept


def pack(source: Path, name: str, game_id: str, scale: float, fps: float, out: Path) -> None:
    loop_flags = loops()
    target = out / game_id
    target.mkdir(parents=True, exist_ok=True)
    manifest = {"name": game_id, "motions": {}}
    for motion, sprute_motion in MOTIONS.items():
        path = source / f"{name}.{sprute_motion}.webp"
        strip = Image.open(path)
        width, height = strip.size
        cell_w, cell_h = width // DIRECTIONS, height
        out_w, out_h = round(cell_w * scale), round(cell_h * scale)
        kept = frames(strip, fps)
        atlas = Image.new("RGBA", (out_w * len(kept), out_h * DIRECTIONS))
        for column, frame in enumerate(kept):
            for row in range(DIRECTIONS):
                cell = frame.crop((row * cell_w, 0, (row + 1) * cell_w, cell_h))
                atlas.paste(cell.resize((out_w, out_h), Image.LANCZOS), (column * out_w, row * out_h))
        atlas.save(target / f"{motion}.webp", quality=88, method=6)
        manifest["motions"][motion] = {
            "file": f"{motion}.webp",
            "frames": len(kept),
            "loop": loop_flags.get(sprute_motion, False),
        }
        manifest.update(cell=[out_w, out_h], fps=fps)
        print(f"{motion:6} <- {path.name}: {len(kept)} frames, {out_w}x{out_h} cells")

    # Feet anchor: bottom-centre of the standing south-facing idle pose.
    idle = Image.open(target / "idle.webp").crop((0, 0, *manifest["cell"]))
    box = idle.getchannel("A").getbbox()
    manifest["anchor"] = [manifest["cell"][0] / 2, box[3] - 2 if box else manifest["cell"][1]]
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    roster_path = out / "characters.json"
    roster = json.loads(roster_path.read_text()) if roster_path.exists() else []
    if game_id not in roster:
        roster.append(game_id)
    roster_path.write_text(json.dumps(roster, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="Folder holding <name>.<motion>.webp strips.")
    parser.add_argument("--name", required=True, help="Character name in the strip filenames.")
    parser.add_argument("--id", help="Name in the game; defaults to --name.")
    parser.add_argument("--scale", type=float, default=0.5)
    parser.add_argument("--fps", type=float, default=12)
    parser.add_argument("--out", type=Path, default=HERE / "characters")
    args = parser.parse_args()
    pack(args.source, args.name, args.id or args.name, args.scale, args.fps, args.out)


if __name__ == "__main__":
    main()
