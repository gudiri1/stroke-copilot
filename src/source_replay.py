"""L0 source adapter. Publishes topic `frame` at the model's frame rate.

Two modes, one contract:
  --dir PATH   replay 8-bit greyscale images from a folder (CathAction clips,
               bench recordings, anything)
  default      synthetic scene, so the chain runs with nothing downloaded

Swapping this process for a SOFA, camera or C-arm adapter changes nothing
downstream. That is the only reason the frame contract exists.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto import messages as M  # noqa: E402
from src import scene  # noqa: E402
from src.bus import Pub, now_ns  # noqa: E402

C = M.CONSTANTS


def iter_dir(path: Path, w: int, h: int):
    import cv2
    files = sorted(p for p in path.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif"})
    if not files:
        raise SystemExit(f"no images in {path}")
    while True:
        for f in files:
            img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            if img.shape != (h, w):
                img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
            yield img


def iter_synthetic(w: int, h: int, loop_s: float = 11.0):
    g = scene.load_graph()
    rng = np.random.default_rng(1)
    t0 = time.monotonic()
    while True:
        t = (time.monotonic() - t0) % loop_s
        img, _ = scene.render(g, t, w, h, rng)
        yield img


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, help="folder of greyscale frames to replay")
    ap.add_argument("--rate", type=float, default=C["frame_rate_hz"])
    ap.add_argument("--count", type=int, default=0, help="stop after N frames (0 = forever)")
    a = ap.parse_args()

    w, h = C["frame_w"], C["frame_h"]
    source = "replay" if a.dir else "synthetic"
    frames = iter_dir(a.dir, w, h) if a.dir else iter_synthetic(w, h)

    pub = Pub()
    period = 1.0 / a.rate
    seq, next_t = 0, time.monotonic()
    print(f"source_replay: {source} {w}x{h} at {a.rate} Hz", flush=True)

    try:
        for img in frames:
            msg = M.Frame(seq=seq, t_capture_ns=now_ns(), w=w, h=h, fmt="mono8",
                          px_mm=C["px_mm"], source=source)
            pub.send("frame", msg, img.tobytes())
            seq += 1
            if a.count and seq >= a.count:
                break
            next_t += period
            time.sleep(max(0.0, next_t - time.monotonic()))
    except KeyboardInterrupt:
        pass
    finally:
        pub.close()
    print(f"source_replay: {seq} frames", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
