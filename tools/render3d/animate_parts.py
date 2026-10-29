"""Animate a T-posed machine mesh (TRELLIS.2 from one drawing) as rigid parts, and render it as game sprite strips.

docs/spikes/3d-render.md, "The stubby, from a T-pose drawing": a drawing of the stubby in a T-pose → TRELLIS.2 → this.
The T-pose places the mesh: the stubs stick out along one axis, which becomes X. The mesh is then cut by its geometry
into body, head (above the neck, the narrowest slice between the stubs and the antenna), the two stubs (outside the
barrel at their height) and the two feet (the bottom slices), each a rigid part on a pivot, and moved by the gait
Materia's stubby moves by (materia-experiments tools/bake/monsters/stubby.ts): an idle bob with a look round, and a
hopping waddle whose roll the head lags. The stubs are first lowered from the T-pose to hang by the body. The antenna
(above the dome) rides on the head and bends after a springy tip, as Materia's does (its `Dangle`), simulated over a
few loops first so each clip loops.

    python tools/render3d/animate_parts.py MESH.glb INPUT.png OUT_DIR --name stubby --clip idle:36 --clip walk:8

writes OUT_DIR/<name>.directions.png, OUT_DIR/<name>.<clip>.webp (2048x256, 12 fps, the four diagonals) and
OUT_DIR/<name>.parts.png (the parts in colour, for checking the cut).
"""
import argparse, math
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from paint_rig import CELL, DIAGONALS, FPS, cell
from render_mesh import matched_gamma, renderer, texture_shade, textured
from rig_mesh import Body

PARTS = ("body", "head", "right stub", "left stub", "right foot", "left foot", "antenna")
COLOURS = torch.tensor([[0.75, 0.75, 0.75], [0.35, 0.6, 0.95], [0.95, 0.45, 0.3], [0.95, 0.8, 0.3], [0.4, 0.8, 0.4], [0.7, 0.4, 0.85],
                        [0.9, 0.3, 0.6]])
MATERIA_HEIGHT = 1.1
LIMIT = math.radians(40)   # how far the antenna bends    # the Materia stubby's height in its own units, which its gait's distances are in


def placed(vertices, height, flip):
    """Stubs along X, facing +Z (or -Z, flipped), standing on y = 0 at the given height, centred."""
    v = vertices - vertices.mean(0)
    horizontal = v[:, [0, 2]]
    far = horizontal.norm(dim=1)
    tips = horizontal[far > far.quantile(0.99)]
    axis = torch.linalg.svd(tips - tips.mean(0), full_matrices=False).Vh[0]     # the stubs' line
    yaw = math.atan2(axis[1].item(), axis[0].item()) + (math.pi if flip else 0.0)
    c, s = math.cos(yaw), math.sin(yaw)
    v = v @ torch.tensor([[c, 0, s], [0, 1, 0], [-s, 0, c]])                     # turns the stubs' line onto X
    v = (v - torch.stack([v[:, 0].mean(), v[:, 1].min(), v[:, 2].mean()])) * height / (v[:, 1].max() - v[:, 1].min())
    return v


def parts(v, height, feet, neck):
    """Which part each vertex is in (index into PARTS), and the pivots: the stubs' shoulders, the neck, the feet."""
    f = v[:, 1] / height
    side = torch.where(v[:, 0] < 0, 0, 1)                       # 0: -X, the figure's right when it faces +Z
    radius = v[:, [0, 2]].norm(dim=1)
    # The barrel's half-width, below the stubs; the stubs are what reaches past it, at their height.
    barrel = v[(f > feet + 0.05) & (f < 0.28), 0].abs().max() * 1.03
    stub = (v[:, 0].abs() > barrel) & (f > feet + 0.05) & (f < 0.62)
    # The neck: the narrowest slice of the rest between the stubs and the antenna.
    rest = ~stub
    slices = torch.arange(0.35, 0.65, 0.01)
    widths = torch.stack([radius[rest & (f >= a) & (f < a + 0.01)].max() for a in slices])
    neck = slices[widths.argmin()].item() + 0.005 if neck is None else neck
    label = torch.zeros(len(v), dtype=torch.long)
    label[f >= neck] = 1
    # The antenna: what rises above the dome, the first slice up from the head's middle narrower than a third of it.
    head = rest & (f >= neck)
    top = f[head].max().item()
    slices = torch.arange(neck + (top - neck) / 2, top, 0.005)
    widths = torch.stack([radius[head & (f >= a) & (f < a + 0.005)].max() for a in slices])
    base = slices[(widths < widths.max() / 3).nonzero()[0, 0]].item()
    antenna = head & (f >= base)
    label[antenna] = 6
    label[stub] = 2 + side[stub]
    low = f < feet
    label[low] = 4 + side[low]
    # It bends from where its nub narrows to the rod (the first slice up within a fifth of the rod's median width),
    # so the nub stays on the dome.
    rod = v[antenna]
    centre = torch.stack([rod[:, 0].mean(), rod[:, 2].mean()])
    width = (rod[:, [0, 2]] - centre).norm(dim=1)
    ups = torch.arange(base * height, rod[:, 1].max().item(), 0.004)
    widths = torch.stack([width[(rod[:, 1] >= a) & (rod[:, 1] < a + 0.004)].max() for a in ups])
    bend = ups[(widths < widths.median() * 1.2).nonzero()[0, 0]]
    pivots = {"neck": torch.tensor([0.0, neck * height, 0.0]),
              "antenna": torch.stack([centre[0], bend, centre[1]]),
              "antenna tip": rod[rod[:, 1] > rod[:, 1].quantile(0.95)].mean(0)}
    for k in (0, 1):
        s = v[stub & (side == k)]
        pivots[PARTS[2 + k]] = torch.stack([torch.sign(s[:, 0].mean()) * barrel, s[:, 1].mean(), s[:, 2].mean()])
        pivots[PARTS[4 + k]] = v[low & (side == k)].mean(0)
    print(f"barrel half-width {barrel:.3f} m, neck at {neck:.3f} of the height, antenna above {base:.3f} bending at {bend / height:.3f}, feet below {feet:.2f}; "
          + ", ".join(f"{p} {(label == i).sum().item()}" for i, p in enumerate(PARTS)))
    return label, pivots


def rotation(x=0.0, y=0.0, z=0.0):
    """XYZ Euler, as three.js applies it (R = Rx Ry Rz, applied to a vector Rz first)."""
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    rx = torch.tensor([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = torch.tensor([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = torch.tensor([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rx @ ry @ rz


def about(pivot, turn=None, move=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
    """4x4: scale and turn about the pivot, then move."""
    m = torch.eye(4)
    m[:3, :3] = (torch.eye(3) if turn is None else turn) @ torch.diag(torch.tensor(scale))
    m[:3, 3] = pivot - m[:3, :3] @ pivot + torch.tensor(move)
    return m


def look(t):
    """The idle's look round in a 3-second loop: ahead, a quick turn to one side and hold, the other, back."""
    keys = [(0.0, 0.0), (0.5, 0.0), (0.7, 0.6), (1.5, 0.6), (1.7, -0.45), (2.5, -0.45), (2.7, 0.0), (3.0, 0.0)]
    for (t0, a0), (t1, a1) in zip(keys, keys[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            return a0 + (a1 - a0) * u * u * (3 - 2 * u)
    return 0.0


def pose(clip, t, seconds, height, pivots, hang):
    """The six parts' 4x4 transforms at time t, by Materia's stubby gait (stubby.ts `moved`), scaled to this height."""
    k = height / MATERIA_HEIGHT
    walk = 0.0 if clip == "idle" else 1.0
    cycles = {"idle": 0, "walk": 1, "run": 2}[clip]
    phase = 2 * math.pi * cycles * t / seconds
    breath = math.sin(2 * math.pi * t / seconds)
    s, c = math.sin(phase), math.cos(phase)
    idle, land = 1 - walk, 1 - abs(s)
    hop = (idle * breath * 0.015 + walk * abs(s) * 0.08) * k
    squash = 1 + idle * breath * 0.012 - walk * land * land * 0.07
    spread = 1 + walk * land * land * 0.04
    ground = torch.zeros(3)
    body = about(ground, rotation(x=walk * 0.1, z=walk * s * 0.13), (0.0, hop, 0.0), (spread, squash, spread))
    head = body @ about(pivots["neck"], rotation(x=-walk * 0.06, y=idle * look(t % 3.0), z=-walk * math.sin(phase - 0.6) * 0.07))
    stubs = [body @ about(pivots[PARTS[2 + i]], rotation(x=walk * s * 0.6 * (1 if i == 0 else -1), z=hang * (1 if i == 0 else -1)))
             for i in (0, 1)]
    feet = []
    for i, lift in enumerate((max(0.0, s), max(0.0, -s))):
        stride = (c if i == 0 else -c) * walk * 0.1 * k
        feet.append(about(pivots[PARTS[4 + i]], rotation(x=-walk * lift * 0.5), (0.0, walk * lift * 0.1 * k, stride)))
    return torch.stack([body, head, *stubs, *feet])


class Dangle:
    """A springy tip on a root (Materia's stubby.ts Dangle, one point): Verlet, pulled to where the part holds it at
    rest, kept at its length from the root, a little weight. Its distances in Materia's units, scaled by k."""

    def __init__(self, root, rest, k, stiff=900.0, fall=0.4, damp=0.86):
        self.root, self.rest, self.length = root, rest, (rest - root).norm()
        self.fall, self.stiff, self.damp = fall * k, stiff, damp
        self.tip = self.before = None

    def step(self, carry, dt):
        """carry: the 4x4 of the part the root rides on, now."""
        root, rest = (carry[:3, :3] @ p + carry[:3, 3] for p in (self.root, self.rest))
        if self.tip is None:
            self.tip, self.before = rest.clone(), rest.clone()
        moving = (self.tip - self.before) * self.damp
        self.before = self.tip.clone()
        tip = self.tip + moving + (rest - self.tip) * min(1.0, self.stiff * dt * dt)
        tip[1] -= self.fall * dt * dt
        rest_way, way = F.normalize(rest - root, dim=0), F.normalize(tip - root, dim=0)
        # A stop: it bends no further than LIMIT, or the run's twice-faster steps set it flopping.
        if (rest_way @ way) < math.cos(LIMIT):
            across = F.normalize(way - rest_way * (rest_way @ way), dim=0)
            way = rest_way * math.cos(LIMIT) + across * math.sin(LIMIT)
        self.tip = root + way * self.length
        return root, rest, self.tip


def swing(clip, frames, height, pivots, hang, stiff, warm=3, rate=120):
    """The antenna's (root, rest tip, tip) at each frame of the loop, the dangle run for `warm` loops first so the loop
    it records has settled (and so starts where it ends)."""
    seconds = frames / FPS
    dangle = Dangle(pivots["antenna"], pivots["antenna tip"], height / MATERIA_HEIGHT, stiff)
    n = round(rate / FPS)
    out = []
    for i in range(-warm * frames, frames):
        for j in range(n):
            t = (i + j / n) / FPS
            state = dangle.step(pose(clip, t % seconds, seconds, height, pivots, hang)[1], 1 / rate)
        if i >= 0:
            out.append(state)
    return out


def bent(positions, rod, state):
    """Turns the antenna's posed vertices above its root about it, from the rest tip's direction to the dangle's, the
    turn eased in over the rod's first quarter so it bends instead of breaking."""
    root, rest, tip = state
    a, b = F.normalize(rest - root, dim=0), F.normalize(tip - root, dim=0)
    axis, angle = torch.cross(a, b, dim=0), torch.acos((a @ b).clamp(-1, 1))
    if angle < 1e-5:
        return positions
    axis = F.normalize(axis, dim=0)
    x = positions[rod] - root
    u = ((x @ a) / (rest - root).norm() / 0.25).clamp(0, 1)
    theta = (angle * u * u * (3 - 2 * u))[:, None]
    turned = x * torch.cos(theta) + torch.cross(axis.expand_as(x), x, dim=1) * torch.sin(theta) + axis * (x @ axis)[:, None] * (1 - torch.cos(theta))
    out = positions.clone()
    out[rod] = root + turned
    return out


def normals_of(positions, faces):
    n = torch.zeros_like(positions)
    a, b, c = positions[faces[:, 0]], positions[faces[:, 1]], positions[faces[:, 2]]
    face = torch.cross(b - a, c - a, dim=1)
    for i in range(3):
        n.index_add_(0, faces[:, i], face)
    return F.normalize(n, dim=-1)


def frame(body, positions, shades):
    out = np.zeros((CELL, CELL * 8, 4), np.uint8)
    normals = normals_of(positions, body.faces)
    for direction in DIAGONALS:
        shade = shades(normals @ renderer.camera(direction, normals.device).T)
        out[:, direction * CELL:(direction + 1) * CELL] = (cell(body, positions, direction, shade).numpy() * 255).round()
    return Image.fromarray(out, "RGBA")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mesh", type=Path)
    parser.add_argument("input", type=Path, help="the drawing the mesh was made from, on white")
    parser.add_argument("out", type=Path)
    parser.add_argument("--name", default="stubby")
    parser.add_argument("--height", type=float, default=1.04, help="metres; the Materia stubby stands 188 px of 256")
    parser.add_argument("--flip", action="store_true", help="face -Z: the stubs' line fixes the yaw only up to front and back")
    parser.add_argument("--feet", type=float, default=0.085, help="the feet are the slices below this fraction of the height")
    parser.add_argument("--neck", type=float, help="fraction of the height; found as the narrowest slice when not given")
    parser.add_argument("--hang", type=float, default=70.0, help="degrees the stubs are lowered from the T-pose")
    parser.add_argument("--stiff", type=float, default=300.0, help="the antenna's spring; Materia's 900 barely shows at 256 px")
    parser.add_argument("--clip", action="append", default=[], help="NAME:FRAMES with NAME idle, walk or run, a loop at 12 fps")
    args = parser.parse_args()
    torch.set_grad_enabled(False)

    vertices, faces, uv, texture = textured(args.mesh)
    v = placed(vertices, args.height, args.flip)
    label, pivots = parts(v, args.height, args.feet, args.neck)
    # The neck bends softly over a couple of centimetres, so the head does not tear from the collar; the rest is rigid.
    neck_y = pivots["neck"][1]
    up = torch.sigmoid((v[:, 1] - neck_y) / 0.006)
    rod = label == 6
    weights = F.one_hot(torch.where(rod, 1, label), 6).float()     # the antenna rides on the head, then bends
    blend = (label <= 1)
    weights[blend, 0], weights[blend, 1] = 1 - up[blend], up[blend]
    gamma = matched_gamma(args.input, uv, texture)
    body = Body(faces)
    homogeneous = torch.cat([v, torch.ones(len(v), 1)], 1)

    def posed(transforms):
        return torch.einsum("vp,pij,vj->vi", weights, transforms, homogeneous)[:, :3]

    def textured_shades(view_normals):
        return texture_shade(faces, uv, texture, gamma, view_normals)

    args.out.mkdir(parents=True, exist_ok=True)
    rest = posed(pose("idle", 0.0, 3.0, args.height, pivots, math.radians(args.hang)))
    frame(body, rest, textured_shades).save(args.out / f"{args.name}.directions.png")
    frame(body, v, lambda n: lambda f, b: COLOURS[label[faces[f, 0]]]).save(args.out / f"{args.name}.parts.png")
    for entry in args.clip:
        clip, frames = entry.rsplit(":", 1)
        frames = int(frames)
        seconds = frames / FPS
        states = swing(clip, frames, args.height, pivots, math.radians(args.hang), args.stiff)
        images = [frame(body, bent(posed(pose(clip, i / FPS, seconds, args.height, pivots, math.radians(args.hang))), rod, states[i]),
                        textured_shades) for i in range(frames)]
        tilt = [math.degrees(math.acos(F.normalize(r - o, dim=0) @ F.normalize(t - o, dim=0))) for o, r, t in states]
        print(f"{clip}: the antenna swings up to {max(tilt):.1f}° off its rest")
        path = args.out / f"{args.name}.{clip}.webp"
        images[0].save(path, save_all=True, append_images=images[1:], duration=round(1000 / FPS), loop=0, lossless=True)
        print(path)


if __name__ == "__main__":
    main()
