"""Check an animation strip, direction by direction, against the character's own direction views.

SCAIL2 sometimes melts a direction, fades it to a ghost, shifts its colours, or turns it to face the
other way; which directions fail depends on the seed. Each drawn direction's frames are measured
against that direction's reference view:

- identity: image-embedding similarity to the reference view. Low when the figure melts.
- facing: similarity to the reference view minus similarity to the opposite view (S against N,
  NE against SW). Below zero reads as turned around, a front where the back should be.
- coverage: opaque area relative to the reference. Low for a ghost or a fragment, high for a smear.
- colour: distance between the mean colours of the figure and the reference, 0 to about 1.7.

The numbers are observations; `verdict` turns them into a pass or fail per direction with the
thresholds in LIMITS. They were set on 20 strips judged frame by frame (goblin, imp and skeleton at
good and bad seeds, 8 and 4 directions): every melt, ghost, colour shift, turn-around and one-frame
glitch seen by eye failed, and every clean direction passed. Facing is not judged for E and W: a side
view looks much like its mirror, so its margin stays near zero either way.
"""
from collections.abc import Callable

import torch

from .layout import STRIP, drawn

LIMITS = {
    "identity": 0.7,         # worst frame's similarity; clean frames stay above 0.8, melts drop below 0.5
    "facing": -0.01,         # a frame below this margin reads as turned around; clean ones sit at +0.03 to +0.15
    "facing_share": 0.3,     # share of frames allowed to read as turned around
    "coverage": (0.6, 1.5),  # opaque area against the reference; clean frames stay within 0.84 to 1.3
    "colour": 0.15,          # mean colour distance; clean frames stay under 0.1, grey or pale skin goes over 0.2
}
SIDE_VIEWS = ("E", "W")


def opposite(name: str) -> str:
    return STRIP[(STRIP.index(name) + 4) % len(STRIP)]


def cells(strip: torch.Tensor, name: str) -> torch.Tensor:
    """One direction's column of a (frames, height, 8 * width, channels) strip."""
    width = strip.shape[2] // len(STRIP)
    index = STRIP.index(name)
    return strip[:, :, index * width:(index + 1) * width]


def on_white(rgb: torch.Tensor, alpha: torch.Tensor) -> torch.Tensor:
    return rgb * alpha[..., None] + (1.0 - alpha[..., None])


def mean_colour(rgb: torch.Tensor, alpha: torch.Tensor) -> torch.Tensor:
    """(frames, 3) alpha-weighted mean colour of each frame's figure."""
    weight = alpha[..., None]
    return (rgb * weight).sum(dim=(1, 2)) / weight.sum(dim=(1, 2)).clamp(min=1e-6)


def measure(frames: torch.Tensor, alpha: torch.Tensor, reference: torch.Tensor, reference_alpha: torch.Tensor,
            embed: Callable[[torch.Tensor], torch.Tensor], directions: int = 8) -> dict:
    """frames (F, H, 8W, 3) with alpha (F, H, 8W), reference (1, H, 8W, 3) with alpha (1, H, 8W), all 0..1.
    `embed` maps (N, h, w, 3) images to (N, D) embeddings. Returns per-direction measurements per frame."""
    names = drawn(directions)
    references = {name: on_white(cells(reference, name), cells(reference_alpha, name)) for name in STRIP}
    reference_embeddings = torch.nn.functional.normalize(embed(torch.cat([references[n] for n in STRIP])), dim=-1)
    by_name = dict(zip(STRIP, reference_embeddings))
    result = {}
    for name in names:
        rgb, a = cells(frames, name), cells(alpha, name)
        embeddings = torch.nn.functional.normalize(embed(on_white(rgb, a)), dim=-1)
        own, other = embeddings @ by_name[name], embeddings @ by_name[opposite(name)]
        reference_a = cells(reference_alpha, name)
        coverage = a.sum(dim=(1, 2)) / reference_a.sum().clamp(min=1e-6)
        colour = (mean_colour(rgb, a) - mean_colour(cells(reference, name), reference_a)).norm(dim=-1)
        result[name] = {
            "identity": [round(v, 4) for v in own.tolist()],
            "facing": [round(v, 4) for v in (own - other).tolist()],
            "coverage": [round(v, 4) for v in coverage.tolist()],
            "colour": [round(v, 4) for v in colour.tolist()],
        }
    return result


def verdict(measurements: dict, limits: dict = LIMITS) -> dict:
    """Pass or fail per direction, with the reasons."""
    out = {}
    for name, m in measurements.items():
        reasons = []
        if min(m["identity"]) < limits["identity"]:
            reasons.append("melts")
        below = sum(v < limits["facing"] for v in m["facing"]) / len(m["facing"])
        if name not in SIDE_VIEWS and below > limits["facing_share"]:
            reasons.append("turned around")
        low, high = limits["coverage"]
        if min(m["coverage"]) < low:
            reasons.append("fades")
        if max(m["coverage"]) > high:
            reasons.append("smears")
        if max(m["colour"]) > limits["colour"]:
            reasons.append("off colour")
        out[name] = {"pass": not reasons, "reasons": reasons}
    return out
