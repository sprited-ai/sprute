"""Render a static textured mesh (a TRELLIS.2 GLB) in the four diagonals, in Sprute's camera and line art.

The simple first step for a Materia machine monster (docs/spikes/3d-render.md): one image of the stubby → TRELLIS.2 →
this, next to Materia's own bake of the stubby. The mesh is placed by matching its silhouettes to the target's
(rig_mesh.fit); its texture is brightened by one gamma so its mean lightness matches the input image's (TRELLIS bakes
its colour de-lit and dark), and lit softly from the front, as the Materia bake and the Sprute heroes are.

    python tools/render3d/render_mesh.py MESH.glb INPUT.png OUT.png --target SE.png NE.png NW.png SW.png
"""
import argparse
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
import trimesh
from PIL import Image
from paint_rig import CELL, DIAGONALS, SHEET, Paint, cell, renderer
from rig_mesh import SIZE, Body, fit

FRONT = F.normalize(torch.tensor([0.0, -0.4, -1.0]), dim=0)    # image space: towards the camera, a little from above


def lightness(rgb):
    return (rgb * torch.tensor([0.2126, 0.7152, 0.0722])).sum(-1)


def textured(path):
    """A TRELLIS.2 GLB: vertices, faces, per-vertex UVs (glTF's v, not trimesh's) and the base colour texture."""
    mesh = trimesh.load(path).to_geometry()
    faces = torch.as_tensor(np.asarray(mesh.faces), dtype=torch.long)
    uv = torch.as_tensor(np.asarray(mesh.visual.uv), dtype=torch.float32) * torch.tensor([1.0, -1.0]) + torch.tensor([0.0, 1.0])   # trimesh flips glTF v
    texture = torch.as_tensor(np.asarray(mesh.visual.material.baseColorTexture.convert("RGB")), dtype=torch.float32).permute(2, 0, 1)[None] / 255
    return torch.as_tensor(np.asarray(mesh.vertices), dtype=torch.float32), faces, uv, texture


def matched_gamma(input_path, uv, texture):
    """One gamma, so the texture's mean lightness is the input image's (over the figure, not the white around it)."""
    image = torch.as_tensor(np.asarray(Image.open(input_path).convert("RGB")), dtype=torch.float32) / 255
    want = lightness(image)[lightness(image) < 0.97].mean()
    used = F.grid_sample(texture, (uv * 2 - 1)[None, None], mode="nearest", align_corners=False)[0, :, 0].T    # texels the mesh uses
    have = lightness(used).clamp(1e-3, 1).mean()
    gamma = (torch.log(want) / torch.log(have)).item()
    print(f"texture lightness {have:.2f}, input {want:.2f}: gamma {gamma:.2f}")
    return gamma


def texture_shade(faces, uv, texture, gamma, view_normals):
    """shade for rasterise: the texture, lit softly from the front."""
    def shade(face, barycentric):
        corners = faces[face]
        at = (uv[corners] * barycentric[..., None]).sum(1)
        colour = F.grid_sample(texture, (at * 2 - 1)[None, None], mode="bilinear", align_corners=False)[0, :, 0].T ** gamma
        n = F.normalize((view_normals[corners] * barycentric[..., None]).sum(1), dim=-1)
        return (colour * (0.78 + 0.3 * (-(n @ FRONT)).clamp(0, 1)[:, None])).clamp(0, 1)
    return shade


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mesh", type=Path)
    parser.add_argument("input", type=Path, help="the image the mesh was made from, on white")
    parser.add_argument("out", type=Path)
    parser.add_argument("--target", type=Path, nargs=4, required=True, help="cut-out cells SE NE NW SW to fit the silhouettes to")
    parser.add_argument("--paint", action="store_true", help="colour by projecting the target cells (paint_rig.Paint) instead of the mesh's texture")
    parser.add_argument("--yaw", type=float, help="degrees; a symmetric silhouette fits as well facing back, so give it")
    parser.add_argument("--height", type=float, default=1.06, help="the figure's height in metres, a first guess for the fit")
    args = parser.parse_args()
    torch.set_grad_enabled(False)

    vertices, faces, uv, texture = textured(args.mesh)
    masks = {d: torch.as_tensor(np.asarray(Image.open(p).getchannel("A").resize((SIZE, SIZE), Image.BILINEAR)) > 128)
             for d, p in zip(DIAGONALS, args.target)}
    box = torch.tensor([[x, y, z] for x in (-0.3, 0.3) for y in (0.0, args.height) for z in (-0.3, 0.3)])
    points = fit(vertices, Body(faces), masks, box, args.yaw)
    normals = F.normalize(torch.as_tensor(np.asarray(trimesh.Trimesh(points.numpy(), faces.numpy(), process=False).vertex_normals), dtype=torch.float32), dim=-1)
    gamma = matched_gamma(args.input, uv, texture)
    body = Body(faces)
    if args.paint:
        # The target cells as paint_rig's 2x2 design sheet, and the placed mesh as a body that is always in its pose.
        sheet = Image.new("RGBA", (CELL * 2, CELL * 2))
        for direction, path in zip(DIAGONALS, args.target):
            column, row = SHEET[direction]
            sheet.paste(Image.open(path).convert("RGBA"), (column * CELL, row * CELL))
        body.skinned = lambda _: (points, normals)
        painted = Paint(body, None, sheet)
    out = np.zeros((CELL, CELL * 8, 4), np.uint8)
    for direction in DIAGONALS:
        shade = painted if args.paint else texture_shade(faces, uv, texture, gamma, normals @ renderer.camera(direction, normals.device).T)
        out[:, direction * CELL:(direction + 1) * CELL] = (cell(body, points, direction, shade).numpy() * 255).round()
    Image.fromarray(out, "RGBA").save(args.out)
    print(args.out)


if __name__ == "__main__":
    main()
