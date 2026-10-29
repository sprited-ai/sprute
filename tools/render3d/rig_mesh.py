"""Put a generated mesh (TRELLIS.2) on a template rig, for paint_rig.py --body (docs/spikes/3d-render.md, next step).

The mesh was generated from a design painted over the rig's reference pose, so it already stands in that pose; it only
has to be turned, scaled and moved onto it. That is found by matching its silhouettes to the design's in the four
diagonals (IoU). Each vertex then takes the skin weights of the nearest point of the rig's own surface in that pose, and
is moved into the rig's bind space, so Sprute's renderer skins it like the rig's own mesh.

    python tools/render3d/rig_mesh.py RIG.glb MESH.glb DESIGN.cut.png OUT.npz --pose Idle
"""
import argparse, math
from pathlib import Path
import numpy as np
import torch
import trimesh
from scipy.spatial import cKDTree
from PIL import Image
from paint_rig import DIAGONALS, SHEET, motion_file, rasterise, renderer

SIZE = 128      # silhouettes are compared at this many pixels a cell


def design_masks(design: Image.Image):
    half = design.width // 2
    return {d: torch.as_tensor(np.asarray(design.crop((c * half, r * half, (c + 1) * half, (r + 1) * half))
                                          .getchannel("A").resize((SIZE, SIZE), Image.BILINEAR)) > 128)
            for d, (c, r) in SHEET.items()}


class Body:
    """Just what rasterise needs."""
    def __init__(self, faces):
        self.faces = faces


def iou(points, body, masks):
    """Mean IoU of the points' silhouettes against the design's, over the four diagonals."""
    total = 0.0
    for direction in DIAGONALS:
        _, mask, _ = rasterise(body, points, direction, SIZE, lambda f, b: torch.zeros(len(f), 3))
        total += ((mask & masks[direction]).sum() / (mask | masks[direction]).sum().clamp(min=1)).item()
    return total / len(DIAGONALS)


def placed(vertices, yaw, pitch, scale, offset):
    """Vertices turned (yaw about Y, then pitch about X), scaled about their centre's foot and moved by offset."""
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    turn = torch.tensor([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @ torch.tensor([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    v = vertices @ turn.T
    low, high = v.min(0).values, v.max(0).values
    foot = torch.stack([(low[0] + high[0]) / 2, low[1], (low[2] + high[2]) / 2])
    return (v - foot) * scale + offset


def fit(vertices, body, masks, reference):
    """Yaw by a full search, then scale, offset and pitch by coordinate descent, all on the IoU."""
    low, high = reference.min(0).values, reference.max(0).values
    target = torch.stack([(low[0] + high[0]) / 2, low[1], (low[2] + high[2]) / 2])
    height = (high[1] - low[1]).item()
    def at(yaw, pitch, scale, offset):
        v = placed(vertices, yaw, pitch, 1.0, torch.zeros(3))
        return placed(vertices, yaw, pitch, scale * height / (v[:, 1].max() - v[:, 1].min()).item(), target + offset)
    best = max(((iou(at(math.radians(y), 0.0, 1.0, torch.zeros(3)), body, masks), y) for y in range(0, 360, 10)))
    params = {"yaw": math.radians(best[1]), "pitch": 0.0, "scale": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}
    steps = {"yaw": math.radians(5), "pitch": math.radians(5), "scale": 0.04, "x": 0.03, "y": 0.02, "z": 0.03}
    score = lambda p: iou(at(p["yaw"], p["pitch"], p["scale"], torch.tensor([p["x"], p["y"], p["z"]])), body, masks)
    current = score(params)
    print(f"yaw search: {best[1]}° IoU {best[0]:.3f}")
    for _ in range(4):
        for key in params:
            for sign in (1, -1):
                trial = dict(params, **{key: params[key] + sign * steps[key]})
                if (s := score(trial)) > current:
                    params, current = trial, s
        steps = {k: v / 2 for k, v in steps.items()}
    print("fit:", {k: round(math.degrees(v), 1) if k in ("yaw", "pitch") else round(v, 3) for k, v in params.items()}, f"IoU {current:.3f}")
    return at(params["yaw"], params["pitch"], params["scale"], torch.tensor([params["x"], params["y"], params["z"]]))


def overlay(points, body, masks, path):
    """Design silhouette in green, the fitted mesh's in magenta, overlap white: SE NE NW SW."""
    out = np.zeros((SIZE, SIZE * 4, 3), np.uint8)
    for k, direction in enumerate(DIAGONALS):
        _, mask, _ = rasterise(body, points, direction, SIZE, lambda f, b: torch.zeros(len(f), 3))
        d, m = masks[direction].numpy(), mask.numpy()
        out[:, k * SIZE:(k + 1) * SIZE] = np.stack([m, d, m], -1) * 255
    Image.fromarray(out).resize((SIZE * 8, SIZE * 2), Image.NEAREST).save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rig", type=Path)
    parser.add_argument("mesh", type=Path)
    parser.add_argument("design", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--pose", default="Idle")
    parser.add_argument("--size", type=float, default=1.0)
    args = parser.parse_args()
    torch.set_grad_enabled(False)
    rig = renderer.Model(args.rig, torch.device("cpu"))
    rig.fit(args.size)
    pose = renderer.sample_motion(rig, motion_file.own(args.rig, args.pose, loop=True), 1, 30)[0]
    reference = rig.world(*pose)
    rig_points, _ = rig.skinned(reference)

    mesh = trimesh.load(args.mesh, force="mesh")
    faces = torch.as_tensor(np.asarray(mesh.faces), dtype=torch.long)
    points = fit(torch.as_tensor(np.asarray(mesh.vertices), dtype=torch.float32), Body(faces), design_masks(Image.open(args.design)), rig_points)

    overlay(points, Body(faces), design_masks(Image.open(args.design)), args.out.with_suffix(".fit.png"))

    # Weights of the nearest point on the rig's surface in the reference pose, from a dense sample of that surface.
    surface = trimesh.Trimesh(rig_points.numpy(), rig.faces.numpy(), process=False)
    samples, triangle = trimesh.sample.sample_surface_even(surface, 400_000, seed=0)
    distance, index = cKDTree(samples).query(points.numpy())
    triangle = triangle[index]
    corners = rig.faces.numpy()[triangle]
    bary = trimesh.triangles.points_to_barycentric(surface.triangles[triangle], samples[index])
    dense = np.zeros((len(rig_points), len(rig.skin_joints)))
    np.add.at(dense, (np.repeat(np.arange(len(rig_points)), 4), rig.joints.numpy().ravel()), rig.weights.numpy().ravel())
    weights = np.einsum("vk,vkj->vj", bary, dense[corners])
    joints = np.argsort(-weights, 1)[:, :4]
    top = np.take_along_axis(weights, joints, 1).clip(min=0)
    top /= top.sum(1, keepdims=True)
    print(f"nearest rig surface: median {np.median(distance) * 100:.1f} cm, 95% {np.percentile(distance, 95) * 100:.1f} cm")

    # Into bind space: undo the reference pose's blended skinning matrix (and the rig's fit to size).
    matrices = reference[rig.skin_joints] @ rig.inverse_bind
    blend = np.einsum("vk,vkij->vij", top, matrices[joints])
    world = (points.numpy() - np.array([0.0, rig.ground, 0.0])) / rig.scale_to
    bind = np.einsum("vij,vj->vi", np.linalg.inv(blend[:, :3, :3]), world - blend[:, :3, 3])
    normals = trimesh.Trimesh(bind, mesh.faces, process=False).vertex_normals
    np.savez(args.out, positions=bind.astype(np.float32), normals=normals.astype(np.float32), faces=np.asarray(mesh.faces),
             joints=joints, weights=top.astype(np.float32))
    print(f"{args.out}: {len(bind)} vertices, {len(mesh.faces)} faces")


if __name__ == "__main__":
    main()
