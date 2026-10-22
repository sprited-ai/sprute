"""Stack an animated WebP's frames into one PNG, a frame per row, and print its frame count and frame seconds.

usage: python3 atlas.py animation.webp atlas.png
"""
import json
import sys

from PIL import Image

source, out = sys.argv[1:3]
with Image.open(source) as animation:
    frames, seconds = [], animation.info.get("duration", 83) / 1000
    for i in range(animation.n_frames):
        animation.seek(i)
        frames.append(animation.convert("RGBA"))
atlas = Image.new("RGBA", (frames[0].width, frames[0].height * len(frames)))
for i, frame in enumerate(frames):
    atlas.paste(frame, (0, i * frame.height))
atlas.save(out)
print(json.dumps({"atlas": out, "frames": len(frames), "seconds": seconds}))
