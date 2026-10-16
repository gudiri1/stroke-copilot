"""L3 Brain — the expert planner.

A deterministic state machine on the vessel graph. It is the expert in the
imitation-learning sense: it can see the 3D model and the target path, which
is privileged information no real system has at inference. Its episodes are
what the student is cloned from, and after that it keeps running beside the
student as the reference the gate compares against.

Deliberately not a learned policy. In front of a clinical jury "the network
decided" is not a defence, so the thing that teaches has to be the thing that
can explain itself.

It also owns the C-arm request. A projection where two branches overlap is
ambiguous no matter how good the perception is — our own node hysteresis below
is the symptom — so when the next bifurcation is unreadable from this angle the
expert asks for a better one. It never moves anything itself: both the advance
and the gantry request go to the gate.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto import messages as M  # noqa: E402
from src import carm, scene  # noqa: E402
from src.bus import Pub, Sub, now_ns  # noqa: E402

C = M.CONSTANTS
CONF_FLOOR = 0.45      # below this the Brain stops claiming to know anything
BIF_NEAR_PX = 55       # distance at which a bifurcation is announced
REACHED_PX = 22
NODE_LOCK_PX = 14      # hold the current edge this close to any node
SEP_MIN = 0.12         # below this the two branches are not tellable apart
SEP_GAIN = 0.10        # only ask for a new view if it buys at least this much


def seg_dist(p, a, b):
    """Distance from p to segment ab, and the parameter t along it."""
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.dist(p, a), 0.0
    t = max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / L2))
    return math.dist(p, (ax + t * vx, ay + t * vy)), t


class Graph:
    """Topology is fixed; pixel positions depend on the current gantry angle."""

    def __init__(self, g: dict):
        self.nodes3 = {k: np.array(v, dtype=float) for k, v in g["nodes"].items()}
        self.edges = [tuple(e) for e in g["edges"]]
        self.route = list(g["target_route"])
        self.route_edges = {frozenset(p) for p in zip(self.route, self.route[1:])}
        self.access = self.route[0]
        self.g = g

        self.adj = {n: [] for n in self.nodes3}
        for a, b in self.edges:
            self.adj[a].append(b)
            self.adj[b].append(a)
        self.degree = {n: len(v) for n, v in self.adj.items()}

        # Hops from the access point. The wire always travels away from access,
        # so the deeper end of an edge is the one ahead of the tip. Euclidean
        # distance is the obvious trap: at a bifurcation the node behind can
        # easily be the farther one.
        self.depth = {self.access: 0}
        q = [self.access]
        while q:
            n = q.pop(0)
            for m in self.adj[n]:
                if m not in self.depth:
                    self.depth[m] = self.depth[n] + 1
                    q.append(m)

        self._key = None
        self.px: dict = {}

    def view(self, alpha: float, beta: float, w: int, h: int) -> None:
        key = (round(alpha, 1), round(beta, 1), w, h)
        if key != self._key:
            self.px = scene.node_px(self.g, alpha, beta, w, h)
            self._key = key

    def nearest_node_px(self, tip) -> float:
        return min(math.dist(tip, p) for p in self.px.values())

    def locate(self, tip, prev_edge=None):
        """(edge, node behind, node ahead, px to the node ahead).

        Within NODE_LOCK_PX of any node the edges meeting there are all equally
        near, and a tip a couple of pixels off the centreline flips between them
        frame to frame. Inside that radius we hold the edge we were already on:
        committing to a branch before the wire has entered it is how you get a
        wrong-branch alarm at every bifurcation, and a co-pilot that cries wolf
        is worse than none.
        """
        best = None
        for a, b in self.edges:
            d, _ = seg_dist(tip, self.px[a], self.px[b])
            if best is None or d < best[0] - 1e-9:
                best = (d, (a, b))
        edge = best[1]
        if prev_edge and self.nearest_node_px(tip) < NODE_LOCK_PX:
            edge = prev_edge
        a, b = edge
        behind, ahead = (a, b) if self.depth[a] < self.depth[b] else (b, a)
        return edge, behind, ahead, math.dist(tip, self.px[ahead])

    def next_on_route(self, node: str):
        if node in self.route:
            i = self.route.index(node)
            if i + 1 < len(self.route):
                return self.route[i + 1]
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--no-carm", action="store_true", help="never request a view change")
    a = ap.parse_args()

    G = Graph(scene.load_graph())
    sub, pub = Sub(["tip"]), Pub()
    n, last_event, cur_edge = 0, "", None
    asked: set = set()
    print(f"brain(expert): target route {' -> '.join(G.route)}", flush=True)

    try:
        while True:
            got = sub.recv(2000)
            if got is None:
                break
            _, tp, _ = got
            G.view(tp.carm_alpha, tp.carm_beta, C["frame_w"], C["frame_h"])

            if not tp.tip_px or tp.conf < CONF_FLOOR:
                pub.send("guidance", M.Guidance(
                    seq=tp.seq, t_ns=now_ns(), node="", next="", dist_px=-1,
                    state="unknown", event="handover", conf=tp.conf))
                pub.send("cmd", M.Cmd(seq=tp.seq, t_ns=now_ns(),
                                      advance_mm_s=0.0, deadman_seq=tp.seq))
                if last_event != "handover":
                    print(f"  [{tp.seq:4d}] handover — conf {tp.conf:.2f}", flush=True)
                    last_event = "handover"
                n += 1
                if a.count and n >= a.count:
                    break
                continue

            tip = (tp.tip_px[0], tp.tip_px[1])
            cur_edge, behind, ahead, dist = G.locate(tip, cur_edge)
            on_path = frozenset(cur_edge) in G.route_edges
            state = "on_path" if on_path else "off_path"

            event = ""
            if not on_path:
                event = "wrong_branch"
            elif ahead == G.route[-1] and dist < REACHED_PX:
                event = "target_reached"
            elif dist < BIF_NEAR_PX and G.degree[ahead] > 2:
                event = "bifurcation_ahead"

            pub.send("guidance", M.Guidance(
                seq=tp.seq, t_ns=now_ns(), node=behind, next=ahead,
                dist_px=int(dist), state=state, event=event, conf=tp.conf))

            # The only command we emit, and the gate still has to pass it.
            speed = C["advance_max_mm_s"] if (on_path and not event) else 0.0
            pub.send("cmd", M.Cmd(seq=tp.seq, t_ns=now_ns(),
                                  advance_mm_s=speed, deadman_seq=tp.seq))

            # Is the branch decision we are about to make readable from here?
            if not a.no_carm and event == "bifurcation_ahead":
                chosen = G.next_on_route(ahead)
                if chosen and (ahead, chosen) not in asked:
                    sib = carm.siblings_of(G.edges, ahead, chosen)
                    cur = carm.score_view(G.g["nodes"], G.edges, ahead, chosen, sib,
                                          tp.carm_alpha, tp.carm_beta)
                    if cur["separation"] < SEP_MIN:
                        best = carm.best_view(G.g["nodes"], G.edges, ahead, chosen, sib)
                        if best["separation"] - cur["separation"] > SEP_GAIN:
                            asked.add((ahead, chosen))
                            print(f"  [{tp.seq:4d}] view is ambiguous at {ahead}: "
                                  f"separation {cur['separation']:.2f} -> "
                                  f"{best['separation']:.2f} at "
                                  f"alpha {best['alpha']:+.0f} beta {best['beta']:+.0f}",
                                  flush=True)
                            pub.send("view", M.View(
                                seq=tp.seq, t_ns=now_ns(),
                                alpha_deg=round(best["alpha"], 1),
                                beta_deg=round(best["beta"], 1),
                                score=round(best["score"], 3),
                                reason="ambiguous_bifurcation"))

            if event and event != last_event:
                print(f"  [{tp.seq:4d}] {event:18s} {behind} -> {ahead}  "
                      f"{dist:5.1f} px  conf {tp.conf:.2f}", flush=True)
            last_event = event
            n += 1
            if a.count and n >= a.count:
                break
    except KeyboardInterrupt:
        pass
    finally:
        sub.close()
        pub.close()
    print(f"brain(expert): {n} messages", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
