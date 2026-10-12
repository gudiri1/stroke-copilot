"""L3 Brain — the state machine on the vessel graph.

Deliberately not a learned policy. Every transition has to be defensible out
loud in front of a clinical jury, and "the network decided" is not a defence.

Publishes `guidance` for the operator and `cmd` for the safety gate. It never
talks to the driver directly: the gate is the only path to motion.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto import messages as M  # noqa: E402
from src import scene  # noqa: E402
from src.bus import Pub, Sub, now_ns  # noqa: E402

C = M.CONSTANTS
CONF_FLOOR = 0.45      # below this the Brain stops claiming to know anything
BIF_NEAR_PX = 55       # distance at which a bifurcation is announced
REACHED_PX = 22
NODE_LOCK_PX = 14      # hold the current edge this close to any node


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
    def __init__(self, g: dict):
        self.nodes = {k: tuple(v) for k, v in g["nodes"].items()}
        self.edges = [tuple(e) for e in g["edges"]]
        self.route = list(g["target_route"])
        self.route_edges = {frozenset(p) for p in zip(self.route, self.route[1:])}
        self.access = self.route[0]

        self.adj = {n: [] for n in self.nodes}
        for a, b in self.edges:
            self.adj[a].append(b)
            self.adj[b].append(a)
        self.degree = {n: len(v) for n, v in self.adj.items()}

        # Hops from the access point. The wire always travels away from access,
        # so the deeper end of an edge is the one ahead of the tip. Using
        # euclidean distance here instead is the obvious trap: at a bifurcation
        # the node behind can easily be the farther one.
        self.depth = {self.access: 0}
        queue = [self.access]
        while queue:
            n = queue.pop(0)
            for m in self.adj[n]:
                if m not in self.depth:
                    self.depth[m] = self.depth[n] + 1
                    queue.append(m)

    def nearest_node_px(self, tip) -> float:
        return min(math.dist(tip, p) for p in self.nodes.values())

    def locate(self, tip, prev_edge=None):
        """(edge, node behind, node ahead, px to the node ahead).

        Within NODE_LOCK_PX of any node the three edges meeting there are all
        equally near, and a tip a couple of pixels off the centreline flips
        between them frame to frame. So inside that radius we hold the edge we
        were already on. Committing to a branch before the wire has actually
        entered it is how you get a 'wrong branch' alarm at every bifurcation,
        and a co-pilot that cries wolf is worse than none.
        """
        best = None
        for a, b in self.edges:
            d, _ = seg_dist(tip, self.nodes[a], self.nodes[b])
            if best is None or d < best[0] - 1e-9:
                best = (d, (a, b))
        edge = best[1]
        if prev_edge and self.nearest_node_px(tip) < NODE_LOCK_PX:
            edge = prev_edge
        a, b = edge
        behind, ahead = (a, b) if self.depth[a] < self.depth[b] else (b, a)
        return edge, behind, ahead, math.dist(tip, self.nodes[ahead])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=0)
    a = ap.parse_args()

    G = Graph(scene.load_graph())
    sub, pub = Sub(["tip"]), Pub()
    n, last_event, cur_edge = 0, "", None
    print(f"brain: target route {' -> '.join(G.route)}", flush=True)

    try:
        while True:
            got = sub.recv(2000)
            if got is None:
                break
            _, tp, _ = got

            if not tp.tip_px or tp.conf < CONF_FLOOR:
                g = M.Guidance(seq=tp.seq, t_ns=now_ns(), node="", next="", dist_px=-1,
                               state="unknown", event="handover", conf=tp.conf)
                pub.send("guidance", g)
                pub.send("cmd", M.Cmd(seq=tp.seq, t_ns=now_ns(),
                                      advance_mm_s=0.0, deadman_seq=tp.seq))
                if g.event != last_event:
                    print(f"  [{tp.seq:4d}] handover — conf {tp.conf:.2f}", flush=True)
                    last_event = g.event
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

            g = M.Guidance(seq=tp.seq, t_ns=now_ns(), node=behind, next=ahead,
                           dist_px=int(dist), state=state, event=event, conf=tp.conf)
            pub.send("guidance", g)

            # The only command we ever emit, and the gate still has to pass it.
            speed = C["advance_max_mm_s"] if (on_path and not event) else 0.0
            pub.send("cmd", M.Cmd(seq=tp.seq, t_ns=now_ns(),
                                  advance_mm_s=speed, deadman_seq=tp.seq))

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
    print(f"brain: {n} messages", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
