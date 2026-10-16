#!/usr/bin/env python3
"""Start the whole chain: broker, source, eyes, brain, viewer.

    python3 tools/run_demo.py                 # synthetic scene, ~15 s
    python3 tools/run_demo.py --dir data/clip # replay a folder of frames
    python3 tools/run_demo.py --seconds 0     # run until Ctrl-C

Each node is a separate process on purpose. If one dies the others keep
running, which is exactly what we want on the day.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--seconds", type=float, default=15.0, help="0 runs until Ctrl-C")
    ap.add_argument("--no-viewer", action="store_true")
    a = ap.parse_args()

    if not (ROOT / "data" / "vessel_graph.json").exists():
        subprocess.run([sys.executable, "src/scene.py"], cwd=ROOT, check=True)
    if not (ROOT / "proto" / "messages.py").exists():
        subprocess.run([sys.executable, "tools/gen_proto.py",
                        "model/model.yaml", "proto/messages.py"], cwd=ROOT, check=True)

    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUNBUFFERED="1")
    nodes = [["src/bus.py"]]
    time.sleep(0)
    procs = [subprocess.Popen([sys.executable, *n], cwd=ROOT, env=env) for n in nodes]
    time.sleep(0.6)                      # let the broker bind before anyone connects

    later = [["src/eyes_stub.py"], ["src/brain.py"], ["src/gate.py"]]
    if not a.no_viewer:
        later.append(["src/viewer.py"])
    src = ["src/source_replay.py"] + (["--dir", str(a.dir)] if a.dir else [])
    later.append(src)                    # source last, so nothing misses frame 0

    for n in later:
        procs.append(subprocess.Popen([sys.executable, *n], cwd=ROOT, env=env))
        time.sleep(0.35)

    try:
        if a.seconds:
            time.sleep(a.seconds)
        else:
            signal.pause()
    except KeyboardInterrupt:
        pass
    finally:
        for p in reversed(procs):
            p.send_signal(signal.SIGINT)
        time.sleep(0.8)
        for p in procs:
            if p.poll() is None:
                p.kill()

    out = sorted((ROOT / "out").glob("frame_*.png"))
    if out:
        print(f"\n{len(out)} overlay frames in out/ — first {out[0].name}, last {out[-1].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
