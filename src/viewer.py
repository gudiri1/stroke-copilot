"""L4 Operator view — overlay on the live image.

Shows a window when there is a display, and writes out/frame_*.png when there
is not, so the same process works on a laptop and in CI.

What the clinician sees is the product. If this looks like a debug dump, the
jury concludes the rest is one too.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto import messages as M  # noqa: E402
from src.bus import Sub, now_ns  # noqa: E402

C = M.CONSTANTS
OUT = Path(__file__).resolve().parent.parent / "out"

INK = (236, 232, 226)
STEEL = (216, 184, 134)      # BGR
ACCENT = (95, 114, 226)
GREEN = (160, 196, 124)


def compose(img: np.ndarray, tip, guid) -> np.ndarray:
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    if tip and tip.wire_px:
        pts = np.array(tip.wire_px, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(vis, [pts], False, STEEL, 1, cv2.LINE_AA)

    if tip and tip.tip_px:
        x, y = int(tip.tip_px[0]), int(tip.tip_px[1])
        colour = ACCENT if (guid and guid.event == "wrong_branch") else GREEN
        cv2.circle(vis, (x, y), 9, colour, 2, cv2.LINE_AA)
        cv2.line(vis, (x - 14, y), (x - 20, y), colour, 1, cv2.LINE_AA)

    bar = vis.shape[0] - 46
    cv2.rectangle(vis, (0, bar), (vis.shape[1], vis.shape[0]), (28, 22, 18), -1)
    f = cv2.FONT_HERSHEY_SIMPLEX

    conf = tip.conf if tip else 0.0
    cv2.putText(vis, f"conf {conf:4.2f}", (12, bar + 29), f, 0.52, INK, 1, cv2.LINE_AA)
    cv2.rectangle(vis, (108, bar + 16), (108 + 90, bar + 26), (70, 62, 56), -1)
    cv2.rectangle(vis, (108, bar + 16), (108 + int(90 * conf), bar + 26),
                  GREEN if conf >= 0.45 else ACCENT, -1)

    if guid:
        txt = f"{guid.state}"
        if guid.next:
            txt += f"  ->{guid.next}  {guid.dist_px}px"
        cv2.putText(vis, txt, (214, bar + 29), f, 0.52, INK, 1, cv2.LINE_AA)
        if guid.event:
            cv2.putText(vis, guid.event.replace("_", " ").upper(),
                        (12, 30), f, 0.68,
                        ACCENT if guid.event in ("wrong_branch", "handover") else GREEN,
                        2, cv2.LINE_AA)
    if tip:
        cv2.putText(vis, f"{tip.latency_ms:.0f} ms", (vis.shape[1] - 86, bar + 29),
                    f, 0.52, (150, 150, 150), 1, cv2.LINE_AA)
    return vis


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--save", action="store_true", help="always write PNGs")
    a = ap.parse_args()

    headless = a.save or not os.environ.get("DISPLAY")
    if headless:
        OUT.mkdir(parents=True, exist_ok=True)

    sub = Sub(["frame", "tip", "guidance"])
    frames, tips, guides = {}, {}, {}
    n = 0
    print(f"viewer: {'writing out/*.png' if headless else 'window'}", flush=True)

    try:
        while True:
            got = sub.recv(2000)
            if got is None:
                break
            topic, msg, payload = got
            if topic == "frame":
                frames[msg.seq] = (msg, payload)
            elif topic == "tip":
                tips[msg.seq] = msg
            else:
                guides[msg.seq] = msg

            ready = [s for s in frames if s in guides]
            for s in sorted(ready):
                f, payload = frames.pop(s)
                img = np.frombuffer(payload, dtype=np.uint8).reshape(f.h, f.w)
                vis = compose(img, tips.pop(s, None), guides.pop(s, None))
                if headless:
                    cv2.imwrite(str(OUT / f"frame_{s:05d}.png"), vis)
                else:
                    cv2.imshow("Stroke Co-pilot", vis)
                    if cv2.waitKey(1) & 0xFF == 27:
                        return 0
                n += 1
            for d in (frames, tips, guides):          # never grow without bound
                for s in sorted(d)[:-60]:
                    d.pop(s, None)
            if a.count and n >= a.count:
                break
    except KeyboardInterrupt:
        pass
    finally:
        sub.close()
        if not headless:
            cv2.destroyAllWindows()
    print(f"viewer: {n} frames", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
