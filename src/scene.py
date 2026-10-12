"""Synthetic fluoroscopy scene, so the whole chain runs before any dataset
or hardware exists.

This is a stand-in, not training data. The perception model is trained and
measured on real frames (CathAction); this scene exists so that on day one
somebody can type `make demo` and watch guidance events appear.

The wire deliberately takes the wrong branch first, then is pulled back and
goes the right way. That is the product demo in twenty seconds, with nothing
plugged in.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

GRAPH_PATH = Path(__file__).resolve().parent.parent / "data" / "vessel_graph.json"

BG, VESSEL, WIRE = 205, 150, 35          # mono8 levels, fluoroscopy-like


def load_graph(path: Path = GRAPH_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _polyline(g: dict, route: list[str]) -> list[tuple[float, float]]:
    return [tuple(g["nodes"][n]) for n in route]


def _walk(pts: list[tuple[float, float]], dist: float) -> list[tuple[float, float]]:
    """Points along a polyline up to `dist` pixels from the start."""
    out = [pts[0]]
    left = dist
    for a, b in zip(pts, pts[1:]):
        seg = math.dist(a, b)
        if left <= 0:
            break
        if seg <= left:
            out.append(b)
            left -= seg
        else:
            t = left / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            left = 0
    return out


def _draw_line(img: np.ndarray, a, b, value: int, width: int) -> None:
    n = max(2, int(math.dist(a, b)))
    xs = np.linspace(a[0], b[0], n)
    ys = np.linspace(a[1], b[1], n)
    r = width // 2
    h, w = img.shape
    for x, y in zip(xs, ys):
        x0, y0 = int(round(x)), int(round(y))
        yy0, yy1 = max(0, y0 - r), min(h, y0 + r + 1)
        xx0, xx1 = max(0, x0 - r), min(w, x0 + r + 1)
        img[yy0:yy1, xx0:xx1] = value


def wire_route(g: dict, t: float) -> tuple[list[str], float]:
    """Where the wire is at time t seconds.

    0.0-4.0 s   advance down the wrong branch
    4.0-5.5 s   pull back
    5.5-11.0 s  advance along the target path
    """
    wrong, target = g["wrong_route"], g["target_route"]
    if t < 4.0:
        return wrong, 60 + t * 52
    if t < 5.5:
        return wrong, 268 - (t - 4.0) * 120
    return target, 88 + (t - 5.5) * 64      # reaches TARGET just before the loop ends


def render(g: dict, t: float, w: int = 512, h: int = 512,
           rng: np.random.Generator | None = None) -> tuple[np.ndarray, tuple[float, float]]:
    """Return (mono8 image, ground-truth tip in pixels)."""
    rng = rng or np.random.default_rng(0)
    img = np.full((h, w), BG, dtype=np.float32)

    for a, b in g["edges"]:
        _draw_line(img, g["nodes"][a], g["nodes"][b], VESSEL, 11)

    route, dist = wire_route(g, t)
    pts = _walk(_polyline(g, route), dist)
    for a, b in zip(pts, pts[1:]):
        _draw_line(img, a, b, WIRE, 3)
    tip = pts[-1]

    # Poisson-ish quantum noise plus a slow vignette: enough texture that a
    # naive global threshold is not automatically correct.
    img += rng.normal(0, 4.0, img.shape)
    yy, xx = np.mgrid[0:h, 0:w]
    img -= 18 * (((xx - w / 2) ** 2 + (yy - h / 2) ** 2) / (w * h)) * 2.0
    return np.clip(img, 0, 255).astype(np.uint8), tip


DEFAULT_GRAPH = {
    "nodes": {
        "ACCESS": [256, 496],
        "BIF1":   [256, 352],
        "LEFT":   [150, 232],
        "DEADEND": [96, 120],
        "RIGHT":  [356, 240],
        "TARGET": [404, 112],
    },
    "edges": [["ACCESS", "BIF1"], ["BIF1", "LEFT"], ["LEFT", "DEADEND"],
              ["BIF1", "RIGHT"], ["RIGHT", "TARGET"]],
    "target_route": ["ACCESS", "BIF1", "RIGHT", "TARGET"],
    "wrong_route":  ["ACCESS", "BIF1", "LEFT", "DEADEND"],
    "note": "Topology, not anatomy. Mirrors the tube-and-Y-connector bench phantom.",
}


if __name__ == "__main__":
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(DEFAULT_GRAPH, indent=2), encoding="utf-8")
    print(f"wrote {GRAPH_PATH}")
