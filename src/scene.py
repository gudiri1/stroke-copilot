"""Synthetic fluoroscopy scene in 3D, rendered from a chosen C-arm angle.

A stand-in, not training data. The perception model is trained and measured on
real frames; this scene exists so the whole chain runs on day one, and so the
C-arm problem is visible rather than asserted.

The vessel tree is built so that the two branches at the first bifurcation sit
symmetrically in front of and behind the coronal plane. In the PA view they
project on top of each other and the image genuinely cannot tell them apart.
Rotate towards lateral and they separate. That is the whole argument for
treating the gantry angle as an actuator, and here you can watch it.

Coordinates are patient millimetres: X left, Y posterior to anterior, Z cranial.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from src import carm

GRAPH_PATH = Path(__file__).resolve().parent.parent / "data" / "vessel_graph.json"

BG, VESSEL, WIRE = 205, 150, 35          # mono8 levels, fluoroscopy-like
PX_MM = 0.39                              # 200 mm detector across 512 px


def load_graph(path: Path = GRAPH_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def to_px(xy_mm: np.ndarray, w: int, h: int, px_mm: float = PX_MM) -> np.ndarray:
    """Image millimetres -> pixels. Cranial is up, so the v axis is flipped."""
    xy = np.atleast_2d(xy_mm)
    return np.stack([w / 2 + xy[:, 0] / px_mm, h / 2 - xy[:, 1] / px_mm], axis=1)


def node_px(g: dict, alpha: float, beta: float, w: int, h: int) -> dict:
    """Every node projected into this view, in pixels."""
    names = list(g["nodes"])
    pts = np.array([g["nodes"][n] for n in names], dtype=float)
    return dict(zip(names, to_px(carm.project(pts, alpha, beta), w, h)))


def _draw_line(img: np.ndarray, a, b, value: int, width: int) -> None:
    n = max(2, int(math.dist(a, b)))
    xs, ys = np.linspace(a[0], b[0], n), np.linspace(a[1], b[1], n)
    r, hh, ww = width // 2, img.shape[0], img.shape[1]
    for x, y in zip(xs, ys):
        x0, y0 = int(round(x)), int(round(y))
        img[max(0, y0 - r):min(hh, y0 + r + 1), max(0, x0 - r):min(ww, x0 + r + 1)] = value


def _walk3(pts: list, dist_mm: float) -> list:
    """Points along a 3D polyline up to dist_mm of true arclength."""
    out, left = [pts[0]], dist_mm
    for a, b in zip(pts, pts[1:]):
        seg = math.dist(a, b)
        if left <= 0:
            break
        if seg <= left:
            out.append(b)
            left -= seg
        else:
            t = left / seg
            out.append(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))
            left = 0
    return out


def wire_route(g: dict, t: float) -> tuple[list, float]:
    """Where the wire is at time t seconds, in true millimetres along the path.

    0.0-4.0 s   advance down the wrong branch
    4.0-5.5 s   pull back
    5.5-11.0 s  advance along the target path, reaching it just before the loop ends
    """
    wrong, target = g["wrong_route"], g["target_route"]
    if t < 4.0:
        return wrong, 30 + t * 30
    if t < 5.5:
        return wrong, 150 - (t - 4.0) * 65
    return target, 52.5 + (t - 5.5) * 30


def render(g: dict, t: float, alpha: float = 0.0, beta: float = 0.0,
           w: int = 512, h: int = 512,
           rng: np.random.Generator | None = None) -> tuple[np.ndarray, tuple[float, float]]:
    """Return (mono8 image, ground-truth tip in pixels) for this view."""
    rng = rng or np.random.default_rng(0)
    img = np.full((h, w), BG, dtype=np.float32)
    P = node_px(g, alpha, beta, w, h)

    for a, b in g["edges"]:
        _draw_line(img, P[a], P[b], VESSEL, 11)

    route, dist = wire_route(g, t)
    pts3 = _walk3([tuple(g["nodes"][n]) for n in route], dist)
    pts = to_px(carm.project(np.array(pts3), alpha, beta), w, h)
    for a, b in zip(pts, pts[1:]):
        _draw_line(img, a, b, WIRE, 3)
    tip = (float(pts[-1][0]), float(pts[-1][1]))

    img += rng.normal(0, 4.0, img.shape)
    yy, xx = np.mgrid[0:h, 0:w]
    img -= 18 * (((xx - w / 2) ** 2 + (yy - h / 2) ** 2) / (w * h)) * 2.0
    return np.clip(img, 0, 255).astype(np.uint8), tip


# The two branches at BIF1 are mirrored across the coronal plane: same X and Z,
# opposite Y. In the PA view they land on exactly the same pixels.
DEFAULT_GRAPH = {
    "units": "mm, patient frame: X left, Y posterior-to-anterior, Z cranial",
    "nodes": {
        "ACCESS":  [0, 0, -90],
        "BIF1":    [0, 0, -10],
        "LEFT":    [-28, 40, 55],
        "DEADEND": [-50, 70, 95],
        "RIGHT":   [-28, -40, 55],
        "TARGET":  [-45, -70, 92],
    },
    "edges": [["ACCESS", "BIF1"], ["BIF1", "LEFT"], ["LEFT", "DEADEND"],
              ["BIF1", "RIGHT"], ["RIGHT", "TARGET"]],
    "target_route": ["ACCESS", "BIF1", "RIGHT", "TARGET"],
    "wrong_route": ["ACCESS", "BIF1", "LEFT", "DEADEND"],
    "note": "Topology, not anatomy. Mirrors the tube-and-Y-connector bench phantom, "
            "lifted into 3D so that the PA view is genuinely ambiguous.",
}


if __name__ == "__main__":
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(DEFAULT_GRAPH, indent=2), encoding="utf-8")
    g = DEFAULT_GRAPH
    sib = carm.siblings_of([tuple(e) for e in g["edges"]], "BIF1", "RIGHT")
    pa = carm.score_view(g["nodes"], [tuple(e) for e in g["edges"]], "BIF1", "RIGHT", sib, 0, 0)
    best = carm.best_view(g["nodes"], [tuple(e) for e in g["edges"]], "BIF1", "RIGHT", sib)
    print(f"wrote {GRAPH_PATH}")
    print(f"  PA   alpha=0 beta=0        score {pa['score']:.3f}  "
          f"separation {pa['separation']:.3f}  foreshorten {pa['foreshorten']:.3f}")
    print(f"  best alpha={best['alpha']:+.0f} beta={best['beta']:+.0f}  score {best['score']:.3f}  "
          f"separation {best['separation']:.3f}  foreshorten {best['foreshorten']:.3f}")
