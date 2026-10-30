"""Give a template rig's own mesh the design's silhouette, for paint_rig.py --body (docs/spikes/3d-render.md).

The design was painted over the rig's reference pose, so the rig's mesh already stands where the design does; only its
outline is the template's (the husky's head and ears, no mane). Each vertex is pushed out or in along its normal, in
that pose, until the mesh's outline lies on the design's in all four diagonals: the vertices on a view's outline are
pulled onto the zero of the design's signed distance field there, and a smoothness term carries the push to the
vertices around them. The vertices, faces, joints and skin weights stay the rig's, so the paint and the clips land
where they did; the result is moved back into bind space like rig_mesh.py's.

    python tools/render3d/fit_silhouette.py RIG.glb DESIGN.cut.png OUT.npz --pose Idle
"""
import argparse
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
import trimesh
from PIL import Image
from scipy.ndimage import distance_transform_edt
from paint_rig import DIAGONALS, SHEET, motion_file, rasterise, renderer, view_of
from rig_mesh import Body

SIZE = 256          # pixels a cell, for the outlines
NEAR = 0.03         # metres: a vertex this close to the depth at its pixel is in front there


def design_fields(design: Image.Image):
    """Per diagonal: the design's mask and its signed distance in cell pixels, negative inside."""
    half = design.width // 2
    fields, masks = {}, {}
    for direction, (column, row) in SHEET.items():
        alpha = np.asarray(design.crop((column * half, row * half, (column + 1) * half, (row + 1) * half))
                           .getchannel("A").resize((SIZE, SIZE), Image.BILINEAR)) > 128
        fields[direction] = torch.as_tensor(distance_transform_edt(~alpha) - distance_transform_edt(alpha), dtype=torch.float32)
        masks[direction] = torch.as_tensor(alpha)
    return fields, masks


def welded(positions, faces):
    """Vertices at the same place (split at UV or normal seams) as one, so a push can't open the seam."""
    _, group, = np.unique(np.round(positions.numpy() / 1e-5).astype(np.int64), axis=0, return_inverse=True)
    return torch.as_tensor(group.ravel(), dtype=torch.long)


def outline(points, body, direction):
    """Which vertices lie on the view's outline: within a pixel of its edge, and in front there."""
    depth, mask, _ = rasterise(body, points, direction, SIZE, lambda f, b: torch.zeros(len(f), 3))
    m = mask.float()[None, None]
    edge = (m - (-F.max_pool2d(-m, 3, 1, 1))).clamp(min=0)            # inside pixels next to outside
    edge = F.max_pool2d(edge, 3, 1, 1)[0, 0] > 0
    near = -F.max_pool2d(-torch.where(mask, depth, torch.full_like(depth, 1e3))[None, None], 3, 1, 1)[0, 0]
    at = view_of(points, direction)
    px = (at[:, :2] * SIZE).long().clamp(0, SIZE - 1)
    on = edge[px[:, 1], px[:, 0]] & (at[:, 2] <= near[px[:, 1], px[:, 0]] + NEAR)
    return on, mask


def subdivided(rig, times):
    """The rig's mesh with each triangle split in four, `times` times; a new vertex's normal and skin weights are its
    edge's ends' average."""
    dense = np.zeros((len(rig.positions), len(rig.skin_joints)))
    np.add.at(dense, (np.repeat(np.arange(len(rig.positions)), rig.joints.shape[1]), rig.joints.numpy().ravel()), rig.weights.numpy().ravel())
    attributes = np.concatenate([rig.positions.numpy(), rig.normals.numpy(), dense], 1)
    faces = rig.faces.numpy()
    for _ in range(times):
        attributes, faces = trimesh.remesh.subdivide(attributes, faces)
    joints = np.argsort(-attributes[:, 6:], 1)[:, :4]
    weights = np.take_along_axis(attributes[:, 6:], joints, 1).clip(min=0)
    weights /= weights.sum(1, keepdims=True)
    rig.positions = torch.as_tensor(attributes[:, :3], dtype=torch.float32)
    rig.normals = F.normalize(torch.as_tensor(attributes[:, 3:6], dtype=torch.float32), dim=1)
    rig.faces = torch.as_tensor(faces, dtype=torch.long)
    rig.joints, rig.weights = torch.as_tensor(joints, dtype=torch.long), torch.as_tensor(weights, dtype=torch.float32)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rig", type=Path)
    parser.add_argument("design", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--pose", default="Idle")
    parser.add_argument("--size", type=float, default=1.0)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--smooth", type=float, default=30.0, help="weight of neighbouring vertices moving alike")
    parser.add_argument("--reach", type=float, default=0.25, help="metres a vertex may move, out or in")
    parser.add_argument("--cover", type=float, default=1.0, help="weight of the design's outline pulling the mesh's")
    parser.add_argument("--subdivide", type=int, default=0, help="split every triangle in four this many times first, "
                        "so a low-poly template has the vertices to follow fur and spikes")
    args = parser.parse_args()

    rig = renderer.Model(args.rig, torch.device("cpu"))
    rig.fit(args.size)
    if args.subdivide:
        subdivided(rig, args.subdivide)
    pose = renderer.sample_motion(rig, motion_file.own(args.rig, args.pose, loop=True), 1, 30)[0]
    reference = rig.world(*pose)
    with torch.no_grad():
        start, normals = rig.skinned(reference)
    group = welded(start, rig.faces)
    count = int(group.max()) + 1
    normal = F.normalize(torch.zeros(count, 3).index_add_(0, group, normals), dim=1)[group]
    edges = torch.cat([rig.faces[:, [0, 1]], rig.faces[:, [1, 2]], rig.faces[:, [2, 0]]])
    edges = group[edges]
    edges = edges[edges[:, 0] != edges[:, 1]]
    body = Body(rig.faces)
    fields, masks = design_fields(Image.open(args.design))
    contours = {}
    for direction, m in masks.items():
        edge = m & ~(-F.max_pool2d(-m.float()[None, None], 3, 1, 1)[0, 0]).bool()
        y, x = edge.nonzero(as_tuple=True)
        contours[direction] = torch.stack([x, y], 1).float() + 0.5

    def ious(points):
        out = []
        for direction in DIAGONALS:
            _, mask, _ = rasterise(body, points, direction, SIZE, lambda f, b: torch.zeros(len(f), 3))
            out.append(((mask & masks[direction]).sum() / (mask | masks[direction]).sum()).item())
        return out

    print("IoU before:", " ".join(f"{x:.3f}" for x in ious(start)))
    push = torch.zeros(count, requires_grad=True)
    optimiser = torch.optim.Adam([push], lr=0.004)
    for step in range(args.steps):
        points = start + (push.clamp(-args.reach, args.reach)[group])[:, None] * normal
        silhouette, n = 0.0, 0
        for direction in DIAGONALS:
            with torch.no_grad():
                on, _ = outline(points.detach(), body, direction)
            at = view_of(points[on], direction)
            distance = F.grid_sample(fields[direction][None, None], (at[:, :2] * 2 - 1)[None, None],
                                     mode="bilinear", padding_mode="border", align_corners=False)[0, 0, 0]
            # And the other way: every pixel of the design's outline pulls the nearest outline vertex onto it, so a spike
            # of the design with no vertex near it still gets one.
            pixels = (at[:, :2] * SIZE)
            nearest = torch.cdist(contours[direction], pixels).min(1).values
            silhouette = silhouette + (distance ** 2).sum() + args.cover * (nearest ** 2).sum() * len(distance) / len(nearest)
            n += len(distance)
        smooth = ((push[edges[:, 0]] - push[edges[:, 1]]) ** 2).sum() / 1e-4      # in (cm) squared
        loss = silhouette / max(n, 1) + args.smooth * smooth / len(edges)
        optimiser.zero_grad()
        loss.backward()
        optimiser.step()
        if step % 50 == 0 or step == args.steps - 1:
            print(f"step {step}: outline {(silhouette / max(n, 1)).item() ** 0.5:.2f} px rms, push {push.abs().max().item() * 100:.1f} cm max")

    with torch.no_grad():
        points = start + (push.clamp(-args.reach, args.reach)[group])[:, None] * normal
    print("IoU after:", " ".join(f"{x:.3f}" for x in ious(points)))

    # Into bind space with each vertex's own skinning, as rig_mesh.py does.
    matrices = reference[rig.skin_joints] @ rig.inverse_bind
    blend = np.einsum("vk,vkij->vij", rig.weights.numpy().astype(np.float64), matrices[rig.joints.numpy()])
    world = (points.numpy() - np.array([0.0, rig.ground, 0.0])) / rig.scale_to
    bind = np.einsum("vij,vj->vi", np.linalg.inv(blend[:, :3, :3]), world - blend[:, :3, 3])
    faces = rig.faces.numpy()
    normals = trimesh.Trimesh(bind, faces, process=False).vertex_normals
    np.savez(args.out, positions=bind.astype(np.float32), normals=normals.astype(np.float32), faces=faces,
             joints=rig.joints.numpy(), weights=rig.weights.numpy())
    print(f"{args.out}: {len(bind)} vertices")


if __name__ == "__main__":
    main()
