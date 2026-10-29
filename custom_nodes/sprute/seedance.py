"""Animate the driving grid with ByteDance Seedance 2.0 on Replicate, with the user's own API token.

The driving grid and the reference grid go up as data URIs; the token comes from REPLICATE_API_TOKEN and never enters
the graph, so it can't end up in a saved animation's workflow.
"""
import base64
import io
import json
import os
import time
import urllib.request

import av
import numpy as np

API = "https://api.replicate.com/v1/"
MODELS = {"seedance-2.0-fast": "bytedance/seedance-2.0-fast", "seedance-2.0": "bytedance/seedance-2.0"}
FPS = 24
PROMPT = (
    "8 directional character sprite animation. Use [Image1] for the character appearance and style. "
    "Use [Video1] for the motion, timing, eight viewing directions, and 3x3 layout. "
    "Replace each mannequin with the corresponding character view from [Image1]. "
    "Keep the center cell empty, the camera fixed, and each character in its own cell facing the same direction throughout. "
    "{ending} Plain gray background."
)
LOOP = "Continue the same motion cycle for the full duration."
ONCE = "Perform the motion once as in [Video1], then hold its final pose."
# Below this silhouette overlap with the driver, the character didn't do the motion (a still crawl scored 0.12–0.14;
# every motion it followed scored 0.41 or more, on a driver drawn 17% too tall).
MIN_OVERLAP = 0.3
# A cell border brighter than the cells beside it by this much is a drawn grid line (seen at +58; clean runs stay under 2).
MAX_BORDER = 10.0


def prompt(loop: bool) -> str:
    return PROMPT.format(ending=LOOP if loop else ONCE)


def encode_mp4(frames: np.ndarray, fps: int = FPS) -> bytes:
    """(frames, height, width, 3) uint8 to an H.264 mp4."""
    buffer = io.BytesIO()
    with av.open(buffer, "w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = frames.shape[2], frames.shape[1], "yuv420p"
        stream.options = {"crf": "12"}
        for frame in frames:
            container.mux(stream.encode(av.VideoFrame.from_ndarray(frame, format="rgb24")))
        container.mux(stream.encode())
    return buffer.getvalue()


def decode_mp4(content: bytes) -> np.ndarray:
    with av.open(io.BytesIO(content)) as container:
        return np.stack([frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)])


def encode_png(image: np.ndarray) -> bytes:
    from PIL import Image
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()


def data_uri(content: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(content).decode()


def token() -> str:
    value = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not value:
        raise RuntimeError("Seedance needs a Replicate API token: set REPLICATE_API_TOKEN or put it in .env.local")
    return value


def api(path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        API + path, data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def generate(model: str, reference: np.ndarray, driving: np.ndarray, *, seed: int, seconds: int, loop: bool,
             log=print) -> np.ndarray:
    """Seedance's frames for the driving grid, as uint8 (frames, height, width, 3) at its own resolution."""
    body = {"input": {
        "prompt": prompt(loop), "seed": seed, "duration": seconds,
        "resolution": "480p", "aspect_ratio": "1:1", "generate_audio": False,
        "reference_images": [data_uri(encode_png(reference), "image/png")],
        "reference_videos": [data_uri(encode_mp4(driving[:seconds * FPS]), "video/mp4")],
    }}
    prediction = api(f"models/{MODELS[model]}/predictions", body)
    log(f"Seedance {model} prediction {prediction['id']}")
    while prediction["status"] not in ("succeeded", "failed", "canceled"):
        time.sleep(5)
        prediction = api(f"predictions/{prediction['id']}")
    if prediction["status"] != "succeeded":
        raise RuntimeError(f"Seedance {prediction['status']}: {prediction.get('error')}")
    output = prediction["output"]
    with urllib.request.urlopen(output if isinstance(output, str) else output[0]) as response:
        return decode_mp4(response.read())


def silhouettes(grid: np.ndarray, size: int = 64) -> np.ndarray:
    """(frames, H, W, 3) uint8 grid on gray to (8, frames, size, size) bool: where each direction differs from the gray."""
    from PIL import Image
    height, width = grid.shape[1] // 3, grid.shape[2] // 3
    cells = []
    for cell in (0, 1, 2, 3, 5, 6, 7, 8):
        row, column = divmod(cell, 3)
        part = grid[:, row * height:(row + 1) * height, column * width:(column + 1) * width].astype(np.int16)
        foreground = ((np.abs(part - 128).max(-1) > 24) * 255).astype(np.uint8)
        cells.append(np.stack([np.asarray(Image.fromarray(f).resize((size, size), Image.BOX)) > 127 for f in foreground]))
    return np.stack(cells)


def border(grid: np.ndarray) -> float:
    """How much brighter the cell borders are than the cells beside them."""
    gray = grid.astype(np.float32).mean(-1)
    height, width = gray.shape[1], gray.shape[2]
    lines = []
    for x in (width // 3, 2 * width // 3):
        beside = np.concatenate([gray[:, :, x - 12:x - 6], gray[:, :, x + 6:x + 12]], 2)
        lines.append(gray[:, :, x - 2:x + 2].mean() - beside.mean())
    for y in (height // 3, 2 * height // 3):
        beside = np.concatenate([gray[:, y - 12:y - 6], gray[:, y + 6:y + 12]], 1)
        lines.append(gray[:, y - 2:y + 2].mean() - beside.mean())
    return float(max(lines))


def check(driving: np.ndarray, output: np.ndarray) -> dict:
    """Did Seedance do the motion in the grid? Both are uint8 grids on gray at any size; frames line up from the first."""
    frames = min(len(driving), len(output))
    driver, result = silhouettes(driving[:frames]), silhouettes(output[:frames])
    overlap = (driver & result).sum((2, 3)) / np.maximum((driver | result).sum((2, 3)), 1)
    report = {"overlap": round(float(overlap.mean()), 3), "border": round(border(output), 1)}
    problems = []
    if report["overlap"] < MIN_OVERLAP:
        problems.append(f"the character doesn't follow the motion (overlap {report['overlap']} < {MIN_OVERLAP})")
    if report["border"] > MAX_BORDER:
        problems.append(f"grid lines between the cells (border {report['border']} > {MAX_BORDER})")
    return report | {"problems": problems}
