"""A small triangle rasterizer in PyTorch: hard z-buffer, pixel centres, barycentric coordinates per pixel.

Enough for the driving-video mannequin (tens of thousands of faces, a few cells per frame) on CPU or GPU.
Faces are grouped by screen size so each batch tests a square of pixels no larger than it needs.
"""
import torch

PIXEL_BUDGET = 4_000_000        # pixels tested per batch


def rasterize(points: torch.Tensor, faces: torch.Tensor, width: int, height: int):
    """Nearest face at each pixel.

    points: (V, 3) pixel x, pixel y and depth (smaller is nearer). faces: (F, 3) vertex indices.
    Returns face (height * width,) long, -1 where empty, and barycentric (height * width, 3) weights of each
    face's three corners at the pixel centre.
    """
    device = points.device
    corners = points[faces]                                  # (F, 3, 3)
    xy = corners[..., :2]
    low = xy.amin(1).floor().long()
    high = xy.amax(1).ceil().long() + 1
    low[:, 0].clamp_(0, width); high[:, 0].clamp_(0, width)
    low[:, 1].clamp_(0, height); high[:, 1].clamp_(0, height)
    extent = (high - low).amax(1)
    area = _edge(xy[:, 0], xy[:, 1], xy[:, 2])
    visible = ((high - low).amin(1) > 0) & (area != 0)

    pixels = width * height
    depth = torch.full((pixels,), float("inf"), device=device)
    face = torch.full((pixels,), -1, dtype=torch.long, device=device)
    barycentric = torch.zeros((pixels, 3), device=device)

    batches = []
    size = 1
    while True:
        chosen = torch.nonzero(visible & (extent <= size) & (extent > size // 2)).squeeze(1)
        step = max(1, PIXEL_BUDGET // (size * size))
        batches += [(chosen[start:start + step], size) for start in range(0, len(chosen), step)]
        if size >= max(width, height):
            break
        size *= 2

    # Pass 1 finds the nearest depth at each pixel; pass 2 keeps the fragments at that depth.
    for keep in (False, True):
        for chosen, size in batches:
            index, z, weights, owner = _fragments(xy[chosen], corners[chosen, :, 2], area[chosen], low[chosen], size, width, height)
            if not keep:
                depth.scatter_reduce_(0, index, z, reduce="amin")
                continue
            nearest = z == depth[index]
            face[index[nearest]] = chosen[owner[nearest]]
            barycentric[index[nearest]] = weights[nearest]
    return face, barycentric


def _edge(a, b, p):
    """Twice the signed area of (a, b, p)."""
    return (b[..., 0] - a[..., 0]) * (p[..., 1] - a[..., 1]) - (b[..., 1] - a[..., 1]) * (p[..., 0] - a[..., 0])


def _fragments(xy, z, area, low, size, width, height):
    """Pixels inside each face's size×size box: flat pixel index, depth, weights and the face's batch position."""
    device = xy.device
    offsets = torch.arange(size, device=device)
    px = low[:, 0, None, None] + offsets[None, None, :]       # (F, 1, size)
    py = low[:, 1, None, None] + offsets[None, :, None]       # (F, size, 1)
    px, py = torch.broadcast_tensors(px, py)
    centre = torch.stack([px.float() + 0.5, py.float() + 0.5], -1)    # (F, size, size, 2)
    a, b, c = (xy[:, i, None, None, :] for i in range(3))
    weights = torch.stack([_edge(b, c, centre), _edge(c, a, centre), _edge(a, b, centre)], -1) / area[:, None, None, None]
    inside = (weights >= 0).all(-1) & (px < width) & (py < height)
    owner, row, column = torch.nonzero(inside, as_tuple=True)
    weights = weights[owner, row, column]
    index = py[owner, row, column] * width + px[owner, row, column]
    return index, (weights * z[owner]).sum(-1), weights, owner
