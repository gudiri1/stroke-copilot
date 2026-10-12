"""ZeroMQ transport. One broker, many publishers, many subscribers.

Publishers connect to XSUB, subscribers connect to XPUB, the broker forwards.
That indirection is what lets us start the nodes in any order and swap a
source adapter without touching anything downstream.

Wire format per message: [topic, msgpack(header), payload?]
The payload part is only present for frames.
"""
from __future__ import annotations

import os
import sys
import time

import zmq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto import messages as M  # noqa: E402

PUB_ENDPOINT = os.environ.get("SC_PUB", "ipc:///tmp/sc-pub")   # publishers connect here
SUB_ENDPOINT = os.environ.get("SC_SUB", "ipc:///tmp/sc-sub")   # subscribers connect here


def now_ns() -> int:
    return time.time_ns()


class Pub:
    def __init__(self, endpoint: str = PUB_ENDPOINT, settle_s: float = 0.25):
        self.ctx = zmq.Context.instance()
        self.sock = self.ctx.socket(zmq.PUB)
        self.sock.setsockopt(zmq.LINGER, 200)
        self.sock.connect(endpoint)
        # PUB drops anything sent before the connection is established.
        time.sleep(settle_s)

    def send(self, topic: str, msg, payload: bytes | None = None) -> None:
        parts = [topic.encode(), M.pack(msg)]
        if payload is not None:
            parts.append(payload)
        self.sock.send_multipart(parts)

    def close(self) -> None:
        self.sock.close()


class Sub:
    def __init__(self, topics, endpoint: str = SUB_ENDPOINT, settle_s: float = 0.25):
        self.ctx = zmq.Context.instance()
        self.sock = self.ctx.socket(zmq.SUB)
        self.sock.setsockopt(zmq.RCVHWM, 8)        # drop stale frames rather than queue them
        for t in topics:
            self.sock.setsockopt_string(zmq.SUBSCRIBE, t)
        self.sock.connect(endpoint)
        time.sleep(settle_s)

    def recv(self, timeout_ms: int = 1000):
        """Return (topic, message, payload) or None on timeout."""
        if not self.sock.poll(timeout_ms):
            return None
        parts = self.sock.recv_multipart()
        topic = parts[0].decode()
        msg = M.unpack(topic, parts[1])
        payload = parts[2] if len(parts) > 2 else None
        return topic, msg, payload

    def close(self) -> None:
        self.sock.close()


def run_broker(pub_endpoint: str = PUB_ENDPOINT, sub_endpoint: str = SUB_ENDPOINT) -> None:
    ctx = zmq.Context.instance()
    xsub = ctx.socket(zmq.XSUB)
    xsub.bind(pub_endpoint)
    xpub = ctx.socket(zmq.XPUB)
    xpub.bind(sub_endpoint)
    print(f"broker: {pub_endpoint} -> {sub_endpoint}", flush=True)
    try:
        zmq.proxy(xsub, xpub)
    except KeyboardInterrupt:
        pass
    finally:
        xsub.close()
        xpub.close()


if __name__ == "__main__":
    run_broker()
