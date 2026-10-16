"""Generated from model/model.yaml by tools/gen_proto.py. Do not edit.

Regenerate with `make proto`. CI runs `make check`, which fails if this file
is out of date with the model.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import msgpack

__all__ = ["Frame", "Tip", "Guidance", "View", "Cmd", "TOPICS", "CONSTANTS", "pack", "unpack"]

# Constants come straight from the model so no process carries its own copy.
CONSTANTS = {'frame_rate_hz': 7.5, 'frame_period_ms': 133.3, 'frame_w': 512, 'frame_h': 512, 'px_mm': 0.39, 'advance_max_mm_s': 3.0, 'watchdog_ms': 100, 'microstep_nm': 19635}


@dataclass
class Frame:
    seq: int = 0
    t_capture_ns: int = 0
    w: int = 0
    h: int = 0
    fmt: str = ""
    px_mm: float = 0.0
    source: str = ""
    carm_alpha: float = 0.0
    carm_beta: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Frame":
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})

@dataclass
class Tip:
    seq: int = 0
    t_ns: int = 0
    tip_px: list = field(default_factory=list)
    conf: float = 0.0
    wire_px: list = field(default_factory=list)
    latency_ms: float = 0.0
    carm_alpha: float = 0.0
    carm_beta: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Tip":
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})

@dataclass
class Guidance:
    seq: int = 0
    t_ns: int = 0
    node: str = ""
    next: str = ""
    dist_px: int = 0
    state: str = ""
    event: str = ""
    conf: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Guidance":
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})

@dataclass
class View:
    seq: int = 0
    t_ns: int = 0
    alpha_deg: float = 0.0
    beta_deg: float = 0.0
    score: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "View":
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})

@dataclass
class Cmd:
    seq: int = 0
    t_ns: int = 0
    advance_mm_s: float = 0.0
    deadman_seq: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Cmd":
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})


# topic name -> message class
TOPICS = {
    "frame": Frame,
    "tip": Tip,
    "guidance": Guidance,
    "cmd": Cmd,
    "view": View,
    "cmd_gated": Cmd,
    "view_gated": View,
}


def pack(msg) -> bytes:
    """Serialise a message dataclass to a msgpack header."""
    return msgpack.packb(msg.to_dict(), use_bin_type=True)


def unpack(topic: str, raw: bytes):
    """Deserialise a msgpack header into the class the topic declares."""
    cls = TOPICS[topic]
    return cls.from_dict(msgpack.unpackb(raw, raw=False))
