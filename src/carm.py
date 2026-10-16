"""C-arm geometry: projection, view quality, and the optimal-view search.

Why this exists at all: a projection in which two branches overlap is
ambiguous, and no perception model can recover what the geometry threw away.
Our own bifurcation hysteresis in brain.py is the symptom. So the angle is an
actuator in the control loop, not a setting on a camera — and choosing it well
is how the system navigates without leaning on a registered 3D roadmap.

Angles follow the usual convention, in degrees:
    alpha   LAO positive, RAO negative   rotation about the cranio-caudal axis
    beta    CRA positive, CAU negative   tilt towards the head

Patient frame: X patient-left, Y posterior-to-anterior, Z cranial. At
alpha = beta = 0 the beam runs along Y, which is the PA view.

Parallel projection throughout. Magnification changes the scale of the image
but not which segments overlap or how foreshortened they are, and those are
the only two things the score cares about.
"""
from __future__ import annotations

import math

import numpy as np

# Search bounds. Real gantries reach further, but anything past these is
# awkward with a patient and a table in the way.
ALPHA_RANGE = (-90.0, 90.0)
BETA_RANGE = (-40.0, 40.0)
STEP_DEG = 5.0

# Score weights. Separation dominates on purpose: a foreshortened branch you
# can still identify beats a well-drawn one you cannot tell from its sibling.
W_FORESHORTEN, W_SEPARATION, W_CLUTTER = 0.3, 0.5, 0.2
CLUTTER_FULL_MM = 12.0          # distance at which a neighbouring vessel stops mattering


def view_dir(alpha_deg: float, beta_deg: float) -> np.ndarray:
    """Unit vector along the beam, patient towards detector."""
    a, b = math.radians(alpha_deg), math.radians(beta_deg)
    return np.array([math.sin(a) * math.cos(b), math.cos(a) * math.cos(b), math.sin(b)])


def basis(d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Image-plane axes (u right, v down) orthogonal to the beam."""
    up = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(d, up))) > 0.99:          # looking straight along Z
        up = np.array([0.0, 1.0, 0.0])
    u = np.cross(up, d)
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return u, v / np.linalg.norm(v)


def project(points_mm: np.ndarray, alpha_deg: float, beta_deg: float) -> np.ndarray:
    """(N,3) in patient mm -> (N,2) in image mm."""
    d = view_dir(alpha_deg, beta_deg)
    u, v = basis(d)
    p = np.atleast_2d(np.asarray(points_mm, dtype=float))
    return np.stack([p @ u, p @ v], axis=1)


def foreshortening(seg_mm: np.ndarray, alpha_deg: float, beta_deg: float) -> float:
    """1.0 when the segment lies in the image plane, 0.0 when it points at the detector."""
    s = np.asarray(seg_mm, dtype=float)
    n = np.linalg.norm(s)
    if n < 1e-9:
        return 0.0
    return float(math.sqrt(max(0.0, 1.0 - (float(np.dot(s / n, view_dir(alpha_deg, beta_deg))) ** 2))))


def _seg_point_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    ab = b - a
    L2 = float(ab @ ab)
    if L2 < 1e-12:
        return float(np.linalg.norm(p - a))
    t = max(0.0, min(1.0, float((p - a) @ ab) / L2))
    return float(np.linalg.norm(p - (a + t * ab)))


def score_view(nodes: dict, edges: list, node: str, chosen: str, sibling: str | None,
               alpha_deg: float, beta_deg: float) -> dict:
    """How well this angle resolves the branch decision at `node`.

    Three terms, each meaning one thing, so a bad score can be explained:
      foreshorten  is the branch we are entering drawn at something like its true length
      separation   does it point somewhere visibly different from its sibling
      clutter      does any unrelated vessel lie on top of it
    """
    P = {k: project(np.array([v]), alpha_deg, beta_deg)[0] for k, v in nodes.items()}
    n3, c3 = np.array(nodes[node]), np.array(nodes[chosen])

    fore = foreshortening(c3 - n3, alpha_deg, beta_deg)

    if sibling is None:
        sep = 1.0
    else:
        vc, vs = P[chosen] - P[node], P[sibling] - P[node]
        nc, ns = np.linalg.norm(vc), np.linalg.norm(vs)
        if nc < 1e-6 or ns < 1e-6:
            sep = 0.0
        else:
            cos = float(np.clip(np.dot(vc / nc, vs / ns), -1.0, 1.0))
            sep = math.acos(cos) / math.pi        # 0 when superimposed, 1 when opposed

    mid = (P[node] + P[chosen]) / 2.0
    far = {node, chosen} | ({sibling} if sibling else set())
    others = [e for e in edges if not (set(e) & far)]
    if others:
        clutter = min(_seg_point_dist(mid, P[a], P[b]) for a, b in others)
    else:
        clutter = CLUTTER_FULL_MM
    clut = min(1.0, clutter / CLUTTER_FULL_MM)

    return {"score": W_FORESHORTEN * fore + W_SEPARATION * sep + W_CLUTTER * clut,
            "foreshorten": fore, "separation": sep, "clutter": clut,
            "alpha": alpha_deg, "beta": beta_deg}


def best_view(nodes: dict, edges: list, node: str, chosen: str, sibling: str | None,
              step: float = STEP_DEG) -> dict:
    """Grid search. A few hundred evaluations, milliseconds, and deterministic.

    The expert uses the 3D model here, which is privileged information. The
    student never gets this function — it learns to ask for *a* different view
    when its own confidence drops, which needs no model at all.
    """
    best = None
    a = ALPHA_RANGE[0]
    while a <= ALPHA_RANGE[1] + 1e-9:
        b = BETA_RANGE[0]
        while b <= BETA_RANGE[1] + 1e-9:
            r = score_view(nodes, edges, node, chosen, sibling, a, b)
            if best is None or r["score"] > best["score"]:
                best = r
            b += step
        a += step
    return best


def siblings_of(edges: list, node: str, chosen: str) -> str | None:
    """The other branch leaving `node`, if there is exactly one."""
    out = [b for a, b in edges if a == node and b != chosen] + \
          [a for a, b in edges if b == node and a != chosen]
    return out[0] if len(out) == 1 else (out[0] if out else None)
