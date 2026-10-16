#!/usr/bin/env python3
"""Fault injector — trip the safety gate on demand, with the chain running.

The gate claims six conditions. A claim a jury cannot see fail is a slide,
not a safety argument, so this process plays the misbehaving student while
the real demo runs:

    make demo &                          # or in another terminal
    python3 tools/fault.py deviation     # student disagrees with the expert
    python3 tools/fault.py rate          # student asks for 9 mm/s
    python3 tools/fault.py interlock     # gantry request while the wire moves

It publishes on the same topics the policies use and touches nothing else.
That is the point: the gate does not know who is talking to it, so there is
no demo path around it.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto import messages as M  # noqa: E402
from src.bus import Pub, Sub, now_ns  # noqa: E402

C = M.CONSTANTS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["deviation", "rate", "interlock"])
    ap.add_argument("--mm-s", type=float, default=9.0)
    ap.add_argument("--timeout", type=float, default=8.0)
    a = ap.parse_args()

    sub, pub = Sub(["cmd"]), Pub()
    print(f"fault: waiting for a live command to hijack ({a.what})", flush=True)
    try:
        deadline_ms = int(a.timeout * 1000)
        while deadline_ms > 0:
            got = sub.recv(200)
            deadline_ms -= 200
            if got is None:
                continue
            _, c, _ = got

            if a.what in ("interlock", "rate") and abs(c.advance_mm_s) <= 0.05:
                continue                             # need the wire actually moving

            if a.what == "interlock":
                pub.send("view", M.View(seq=c.seq, t_ns=now_ns(), alpha_deg=-70.0,
                                        beta_deg=40.0, score=0.70, reason="injected_fault"))
                print(f"fault: asked for a gantry move at seq {c.seq} while the wire "
                      f"was advancing at {c.advance_mm_s:.2f} mm/s", flush=True)
                return 0

            # "rate" stays inside the deviation bound on purpose, so the
            # clamp is what the jury sees rather than the deviation veto.
            want = (c.advance_mm_s + 1.4) if a.what == "rate" else c.advance_mm_s + 4.0
            pub.send("cmd", M.Cmd(seq=c.seq, t_ns=now_ns(),
                                  advance_mm_s=want, deadman_seq=c.seq))
            print(f"fault: published {want:+.2f} mm/s on seq {c.seq}, "
                  f"against the expert's {c.advance_mm_s:+.2f}", flush=True)
            return 0
        print("fault: no command seen — is the demo running?", flush=True)
        return 1
    finally:
        sub.close()
        pub.close()


if __name__ == "__main__":
    raise SystemExit(main())
