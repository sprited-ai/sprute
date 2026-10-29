"""Spike (docs/spikes/3d-render.md): render a rigged GLB in the look of a design painted over it, as a 4-direction strip.

The design is a 2x2 sheet (NW NE / SW SE, cut out) that was painted over the rig's reference pose rendered by Sprute's
renderer, as experiments/monster-quadruped did for the dusk wolf. Every point of the mesh takes its colour from the
design views that see it in that reference pose (projective texturing, so the rig needs no UVs), and then follows the
rig through any of its clips. No diffusion model runs: every frame is a rasterised mesh, so a direction cannot turn
around, melt or grow legs.

    python tools/render3d/paint_rig.py RIG.glb DESIGN.cut.png OUT_DIR --pose Idle --clip Idle:40 --clip Walk:12

writes OUT_DIR/<name>.directions.png and OUT_DIR/<name>.<clip>.webp (2048x256, 12 fps, S E N W transparent), the
layout `sprute animate --directions 4` writes. Runs on a laptop CPU in about a second a frame.
"""
import argparse, importlib, sys, time, types
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

pkg = types.ModuleType("sprute_nodes"); pkg.__path__ = [str(Path(__file__).resolve().parents[2] / "custom_nodes/sprute")]
sys.modules["sprute_nodes"] = pkg
renderer = importlib.import_module("sprute_nodes.renderer")
motion_file = importlib.import_module("sprute_nodes.motion_file")

DIAGONALS = (1, 3, 5, 7)                                   # SE, NE, NW, SW in the strip
SHEET = {5: (0, 0), 3: (1, 0), 7: (0, 1), 1: (1, 1)}      # where each sits in the 2x2 design sheet
FPS, CELL, SS = 12, 256, 3
VISIBLE = 0.03          # metres: a point further behind the reference depth than this is hidden from that view
STEP = 0.06             # metres: a depth step this large between neighbouring pixels is drawn as a line
LINE = 2.2              # line width in cell pixels
INK = torch.tensor([0.16, 0.14, 0.13])


def view_of(points, direction):
    """Points (model space) in a direction's image space, x/y in 0..1 of the cell, z in metres away from the camera."""
    rotation = renderer.camera(direction, points.device)
    view = (points - torch.tensor([0.0, renderer.CENTRE_HEIGHT, 0.0])) @ rotation.T
    return torch.stack([0.5 + renderer.PIXELS_PER_METRE * view[:, 0], 0.5 + renderer.PIXELS_PER_METRE * view[:, 1], view[:, 2]], 1)


def rasterise(model, positions, direction, size, shade):
    """Rasterise a direction at size x size: (depth in metres, mask, shade's output per pixel)."""
    rotation = renderer.camera(direction, positions.device)
    view = (positions - torch.tensor([0.0, renderer.CENTRE_HEIGHT, 0.0])) @ rotation.T
    view[:, 2] += renderer.DISTANCE
    depth = torch.full((size * size,), float("inf"))
    out = torch.zeros((size * size, 3))
    mask = torch.zeros(size * size, dtype=torch.bool)
    renderer._rasterize_person(view, model.faces, renderer.PIXELS_PER_METRE * size * renderer.DISTANCE, size, size, depth, out, mask, shade)
    return (depth - renderer.DISTANCE).view(size, size), mask.view(size, size), out.view(size, size, 3)


class Paint:
    """Colour for a point of the mesh, from the design views that see it in the reference pose."""

    def __init__(self, model, reference, design: Image.Image):
        self.model = model
        self.positions, normals = model.skinned(reference)
        self.normals = F.normalize(normals, dim=-1)
        half = design.width // 2
        self.views, self.depths = {}, {}
        for direction, (column, row) in SHEET.items():
            cell = np.asarray(design.crop((column * half, row * half, (column + 1) * half, (row + 1) * half)).convert("RGBA"), np.float32) / 255
            rgba = torch.as_tensor(cell).permute(2, 0, 1)[None]
            self.views[direction] = torch.cat([rgba[:, :3] * rgba[:, 3:], rgba[:, 3:]], 1)        # premultiplied
            depth, _, _ = rasterise(model, self.positions, direction, 512, lambda f, b: torch.zeros(len(f), 3))
            self.depths[direction] = depth

    def __call__(self, faces, barycentric):
        corners = self.model.faces[faces]
        point = (self.positions[corners] * barycentric[..., None]).sum(1)
        normal = F.normalize((self.normals[corners] * barycentric[..., None]).sum(1), dim=-1)
        colour, weight = torch.zeros(len(point), 3), torch.zeros(len(point), 1)
        fallback, best = torch.zeros(len(point), 3), torch.full((len(point), 1), -1.0)
        for direction, view in self.views.items():
            at = view_of(point, direction)
            facing = -(normal @ renderer.camera(direction, point.device).T)[:, 2:3]    # 1 when it faces the camera
            grid = (at[:, :2] * 2 - 1)[None, None]
            sample = F.grid_sample(view, grid, mode="bilinear", align_corners=False)[0, :, 0].T       # (n, 4)
            near = F.grid_sample(-F.max_pool2d(-self.depths[direction][None, None], 5, 1, 2), grid, mode="nearest", align_corners=False)[0, 0, 0]
            seen = (at[:, 2] <= near + VISIBLE).float()[:, None]
            w = facing.clamp(min=0) ** 2 * seen * sample[:, 3:]
            colour += w * sample[:, :3] / sample[:, 3:].clamp(min=1e-3)
            weight += w
            # A point no view sees (a paw's sole, under the belly) takes the paint where it lands in the view it faces
            # most, so it keeps the colour of the part around it instead of the background's.
            score = (facing + 1.5) * sample[:, 3:]
            fallback = torch.where(score > best, sample[:, :3] / sample[:, 3:].clamp(min=1e-3), fallback)
            best = torch.maximum(best, score)
        painted = colour / weight.clamp(min=1e-6)
        return torch.where(weight > 1e-3, painted, fallback)


def cell(model, positions, direction, paint):
    """One RGBA cell: painted colour, with a line of even width on the silhouette and wherever one part is in front of
    another, rendered at SS times the cell and averaged down, so the line is anti-aliased."""
    size = CELL * SS
    depth, mask, colour = rasterise(model, positions, direction, size, paint)
    inside = mask.float()
    d = torch.where(mask, depth, torch.full_like(depth, 1e3))
    edge = torch.zeros_like(inside)
    for dy, dx in ((0, 1), (1, 0)):
        a, b = inside, torch.roll(inside, (-dy, -dx), (0, 1))
        da, db = d, torch.roll(d, (-dy, -dx), (0, 1))
        step = ((a != b) | ((a * b > 0) & ((da - db).abs() > STEP))).float()
        step[size - 1:] *= 1 - dy                     # roll wraps round the border: no edge across it
        step[:, size - 1:] *= 1 - dx
        edge = torch.maximum(edge, step)
        edge = torch.maximum(edge, torch.roll(step, (dy, dx), (0, 1)))
    radius = int(round(LINE * SS / 2))
    yy, xx = torch.meshgrid(torch.arange(-radius, radius + 1), torch.arange(-radius, radius + 1), indexing="ij")
    disc = ((yy ** 2 + xx ** 2) <= radius ** 2 + 0.5).float()[None, None]
    ink = (F.conv2d(edge[None, None], disc, padding=radius)[0, 0] > 0).float()
    # The ink is the colour under it taken dark, as the Materia bake does; outside the body it is the nearest colour's.
    under = F.max_pool2d((colour * inside[..., None]).permute(2, 0, 1)[None], 2 * radius + 1, 1, radius)[0].permute(1, 2, 0)
    under = torch.where(mask[..., None], colour, under)
    rgb = torch.where(ink[..., None] > 0, under * 0.38 + INK * 0.6, colour)
    alpha = torch.maximum(inside, ink)
    rgba = torch.cat([rgb * alpha[..., None], alpha[..., None]], -1).permute(2, 0, 1)[None]
    rgba = F.avg_pool2d(rgba, SS)[0].permute(1, 2, 0)
    return torch.cat([rgba[..., :3] / rgba[..., 3:].clamp(min=1e-6), rgba[..., 3:]], -1).clamp(0, 1)


def strip(model, poses, paint, drawn=DIAGONALS):
    frames = []
    for rotations, hips, offsets in poses:
        positions, _ = model.skinned(model.world(rotations, hips, offsets))
        out = np.zeros((CELL, CELL * 8, 4), np.uint8)
        for direction in drawn:
            out[:, direction * CELL:(direction + 1) * CELL] = (cell(model, positions, direction, paint).numpy() * 255).round()
        frames.append(Image.fromarray(out, "RGBA"))
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rig", type=Path)
    parser.add_argument("design", type=Path, help="the 2x2 design sheet (NW NE / SW SE), cut out")
    parser.add_argument("out", type=Path)
    parser.add_argument("--name", default="monster")
    parser.add_argument("--pose", default="Idle", help="the clip whose first frame the design was painted over")
    parser.add_argument("--size", type=float, default=1.0, help="the rig's longest side in metres, as Render Rig takes it")
    parser.add_argument("--directions", type=int, choices=(4, 8), default=4, help="8 also draws S, E, N and W, painted from their neighbours")
    parser.add_argument("--clip", action="append", default=[], help="NAME:FRAMES, the clip played once over FRAMES at 12 fps")
    args = parser.parse_args()
    torch.set_grad_enabled(False)
    model = renderer.Model(args.rig, torch.device("cpu"))
    model.fit(args.size)
    reference = renderer.sample_motion(model, motion_file.own(args.rig, args.pose, loop=True), 1, 30)[0]
    paint = Paint(model, model.world(*reference), Image.open(args.design))
    drawn = DIAGONALS if args.directions == 4 else tuple(range(8))
    args.out.mkdir(parents=True, exist_ok=True)
    strip(model, [reference], paint, drawn)[0].save(args.out / f"{args.name}.directions.png")
    for entry in args.clip:
        clip, frames = entry.rsplit(":", 1)
        frames = int(frames)
        motion = motion_file.own(args.rig, clip, loop=True)
        seconds = len(motion[4]) / motion[1]
        started = time.time()
        images = strip(model, renderer.sample_motion(model, motion, frames, frames / seconds), paint, drawn)
        path = args.out / f"{args.name}.{clip.lower()}.webp"
        images[0].save(path, save_all=True, append_images=images[1:], duration=round(1000 / FPS), loop=0, lossless=True)
        print(f"{path}: {frames} frames in {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
