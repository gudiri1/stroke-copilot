"""L1 Eyes — placeholder perception, so the chain is complete on day one.

This is a classical threshold detector, not the product. It exists to hold the
contract open while [AI] trains the real model. Replace this file; publish the
same `tip` message and nothing else in the system changes.

Deliberately real in one respect: the confidence it reports falls when the tip
jumps between frames. A confidence that only tracks image brightness would let
the safety gate pass nonsense, so even the stub earns its number.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto import messages as M  # noqa: E402
from src import scene  # noqa: E402
from src.bus import Pub, Sub, now_ns  # noqa: E402

C = M.CONSTANTS
WIRE_MAX = 90          # mono8 level below which a pixel may be wire
EXPECT_PX = 400        # a plausible wire footprint; below this, confidence falls
JUMP_SCALE = 40.0      # px of frame-to-frame tip motion that halves confidence


def detect(img: np.ndarray, access: tuple[float, float]):
    """Return (tip_xy, wire_polyline, raw_confidence) or (None, [], 0.0)."""
    ys, xs = np.nonzero(img < WIRE_MAX)
    if xs.size < 20:
        return None, [], 0.0

    d = np.hypot(xs - access[0], ys - access[1])
    order = np.argsort(d)
    xs, ys, d = xs[order], ys[order], d[order]

    tip = (float(xs[-1]), float(ys[-1]))
    step = max(1, xs.size // 24)
    poly = [[float(xs[i]), float(ys[i])] for i in range(0, xs.size, step)]

    coverage = min(1.0, xs.size / EXPECT_PX)
    return tip, poly, coverage


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=0)
    a = ap.parse_args()

    g = scene.load_graph()
    access = tuple(g["nodes"][g["target_route"][0]])

    sub, pub = Sub(["frame"]), Pub()
    prev_tip, n = None, 0
    print("eyes_stub: running (threshold placeholder, replace with the model)", flush=True)

    try:
        while True:
            got = sub.recv(2000)
            if got is None:
                break
            _, f, payload = got
            img = np.frombuffer(payload, dtype=np.uint8).reshape(f.h, f.w)

            tip, poly, cov = detect(img, access)
            if tip is None:
                conf = 0.0
                tip_out = []
            else:
                jump = math.dist(tip, prev_tip) if prev_tip else 0.0
                conf = float(cov * math.exp(-jump / JUMP_SCALE))
                prev_tip, tip_out = tip, [tip[0], tip[1]]

            pub.send("tip", M.Tip(
                seq=f.seq, t_ns=now_ns(), tip_px=tip_out, conf=round(conf, 3),
                wire_px=poly, latency_ms=round((now_ns() - f.t_capture_ns) / 1e6, 2)))
            n += 1
            if a.count and n >= a.count:
                break
    except KeyboardInterrupt:
        pass
    finally:
        sub.close()
        pub.close()
    print(f"eyes_stub: {n} frames", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
