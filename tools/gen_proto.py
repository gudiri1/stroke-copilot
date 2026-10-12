#!/usr/bin/env python3
"""Generate proto/messages.py from model/model.yaml.

The model is the single source of truth. Every process imports the generated
module instead of hand-writing a dict layout, so a field added in the model
reaches both ends of the wire or neither.

Fails loudly when a flow names a type that does not exist, which is the whole
reason to run it in CI (`make check`).

    python3 tools/gen_proto.py model/model.yaml proto/messages.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

PY = {
    "u8": "int", "u16": "int", "u32": "int", "u64": "int",
    "i8": "int", "i16": "int", "i32": "int", "i64": "int",
    "f32": "float", "f64": "float",
    "str": "str", "bool": "bool", "list": "list", "bytes": "bytes",
}
DEFAULT = {"int": "0", "float": "0.0", "str": '""', "bool": "False",
           "list": "field(default_factory=list)", "bytes": 'b""'}

HEAD = '''"""Generated from model/model.yaml by tools/gen_proto.py. Do not edit.

Regenerate with `make proto`. CI runs `make check`, which fails if this file
is out of date with the model.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import msgpack

__all__ = [{all_names}, "TOPICS", "CONSTANTS", "pack", "unpack"]

# Constants come straight from the model so no process carries its own copy.
CONSTANTS = {constants}

'''

TPL = '''
@dataclass
class {cls}:
{fields}
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "{cls}":
        return cls(**{{k: v for k, v in d.items() if k in cls.__annotations__}})
'''

TAIL = '''

# topic name -> message class
TOPICS = {topics}


def pack(msg) -> bytes:
    """Serialise a message dataclass to a msgpack header."""
    return msgpack.packb(msg.to_dict(), use_bin_type=True)


def unpack(topic: str, raw: bytes):
    """Deserialise a msgpack header into the class the topic declares."""
    cls = TOPICS[topic]
    return cls.from_dict(msgpack.unpackb(raw, raw=False))
'''


def main(model_path: str, out_path: str) -> int:
    model = yaml.safe_load(Path(model_path).read_text(encoding="utf-8"))
    types = model.get("types") or {}
    flows = model.get("flows") or {}
    constants = model.get("constants") or {}

    missing = sorted({f["type"] for f in flows.values()} - set(types))
    if missing:
        print(f"error: flows reference undefined types: {', '.join(missing)}", file=sys.stderr)
        return 1

    unused = sorted(set(types) - {f["type"] for f in flows.values()})
    if unused:
        print(f"warning: types defined but carried by no flow: {', '.join(unused)}", file=sys.stderr)

    body = []
    for name, spec in types.items():
        lines = []
        for fname, ftype in spec.items():
            py = PY.get(ftype)
            if py is None:
                print(f"error: unknown wire type {ftype!r} on {name}.{fname}", file=sys.stderr)
                return 1
            lines.append(f"    {fname}: {py} = {DEFAULT[py]}")
        body.append(TPL.format(cls=name, fields="\n".join(lines) + "\n"))

    topics = "{\n" + "".join(
        f'    "{t}": {f["type"]},\n' for t, f in flows.items()
    ) + "}"

    src = (
        HEAD.format(
            all_names=", ".join(f'"{n}"' for n in types),
            constants=repr(constants),
        )
        + "".join(body)
        + TAIL.format(topics=topics)
    )

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(src, encoding="utf-8")
    print(f"wrote {out} — {len(types)} types, {len(flows)} topics")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(*args))
