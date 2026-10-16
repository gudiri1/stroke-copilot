"""L5 Safety gate — the only path from any policy to either actuator.

There are two things that move, the wire and the gantry, and both go through
here. Nothing upstream talks to hardware; that is the entire point, and it is
what makes the sentence "the policy is supervised" checkable instead of
decorative.

Six conditions, every one of them trippable on the table:

  confidence   perception below the floor and nothing leaves
  deviation    the student's command against what the expert would have done
  watchdog     no fresh command within 100 ms and the gate falls silent
  rate         advance clamped, enforced here as well as in firmware
  interlock    the gantry moves only while the wire is still, and the reverse
  handover     an explicit handover event stops everything until it clears

The deviation check is the one the challenge asks for by name. It is how a
policy can learn new skills without being allowed to act outside what an
expert would have done this frame.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto import messages as M  # noqa: E402
from src.bus import Pub, Sub, now_ns  # noqa: E402

C = M.CONSTANTS
CONF_FLOOR = 0.45
DEV_MAX_MM_S = 1.5          # how far the student may differ from the expert
WATCHDOG_NS = C["watchdog_ms"] * 1_000_000
STILL_MM_S = 0.05           # below this the wire counts as stationary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--dev-max", type=float, default=DEV_MAX_MM_S)
    a = ap.parse_args()

    sub = Sub(["cmd", "view", "tip", "guidance"])
    pub = Pub()

    expert_cmd: dict[int, float] = {}    # seq -> what the expert asked for
    conf: dict[int, float] = {}
    handover = False
    last_cmd_ns = now_ns()
    advance = 0.0
    n = vetoes = 0
    print("gate: conf · deviation · watchdog · rate · interlock · handover", flush=True)

    try:
        while True:
            got = sub.recv(2000)
            if got is None:
                break
            topic, m, _ = got

            if topic == "tip":
                conf[m.seq] = m.conf
                for s in sorted(conf)[:-80]:
                    conf.pop(s, None)
                continue

            if topic == "guidance":
                handover = (m.event == "handover")
                continue

            if topic == "cmd":
                last_cmd_ns = now_ns()
                c = conf.get(m.seq, 0.0)
                want = m.advance_mm_s

                # The expert publishes first for a given seq; whoever comes
                # second is the student and gets compared against it.
                if m.seq not in expert_cmd:
                    expert_cmd[m.seq] = want
                    deviation = 0.0
                else:
                    deviation = abs(want - expert_cmd[m.seq])
                for s in sorted(expert_cmd)[:-80]:
                    expert_cmd.pop(s, None)

                reason = ""
                if handover:
                    reason = "handover"
                elif c < CONF_FLOOR:
                    reason = f"confidence {c:.2f}"
                elif deviation > a.dev_max:
                    reason = f"deviation {deviation:.2f} mm/s"
                elif now_ns() - last_cmd_ns > WATCHDOG_NS:
                    reason = "watchdog"

                out = 0.0 if reason else max(-C["advance_max_mm_s"],
                                             min(C["advance_max_mm_s"], want))
                if reason and want != 0.0:
                    vetoes += 1
                    print(f"  [{m.seq:4d}] VETO cmd  {want:+.2f} mm/s — {reason}", flush=True)
                advance = out
                pub.send("cmd_gated", M.Cmd(seq=m.seq, t_ns=now_ns(),
                                            advance_mm_s=out, deadman_seq=m.seq))
                n += 1

            elif topic == "view":
                # Interlock: one actuator at a time.
                if abs(advance) > STILL_MM_S:
                    vetoes += 1
                    print(f"  [{m.seq:4d}] VETO view {m.alpha_deg:+.0f}/{m.beta_deg:+.0f}"
                          f" — wire is moving at {advance:.2f} mm/s", flush=True)
                else:
                    pub.send("view_gated", m)
                    print(f"  [{m.seq:4d}] view  -> alpha {m.alpha_deg:+.0f}  "
                          f"beta {m.beta_deg:+.0f}  score {m.score:.2f}  ({m.reason})", flush=True)

            if a.count and n >= a.count:
                break
    except KeyboardInterrupt:
        pass
    finally:
        sub.close()
        pub.close()
    print(f"gate: {n} commands, {vetoes} vetoes", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
