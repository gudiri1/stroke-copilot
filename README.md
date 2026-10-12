# Stroke Co-pilot

Robotics & AI Hackathon 2026, Siemens Healthineers Innovation Center Erlangen,
22–24 October. Challenge 1, *Improve Endovascular Procedures*.

An AI co-pilot that tracks the guidewire on the existing X-ray stream, warns
before the wrong branch, guides the operator by voice, and may command a wire
driver through a single safety gate.

**Research prototype. Not a medical device. No patient data at any stage —
phantom, simulation and open datasets only.**

---

## Run it right now

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
make demo
```

No dataset, no hardware, no network. A synthetic scene drives the full chain
and the wire deliberately takes the wrong branch first, so the console prints
the product in six lines:

```
[   5] bifurcation_ahead  ACCESS -> BIF1   49.0 px  conf 0.61
[  15] wrong_branch       BIF1 -> LEFT    138.9 px  conf 0.82
[  39] bifurcation_ahead  ACCESS -> BIF1   18.0 px  conf 0.64
[  79] target_reached     RIGHT -> TARGET  19.9 px  conf 0.81
[  83] handover —         conf 0.00
```

Overlay frames land in `out/`. With a display, `src/viewer.py` opens a window
instead.

## The architecture in one paragraph

Four interchangeable image sources publish one `frame` contract. Everything
downstream is fixed: **Eyes** segments the wire and reports a tip with a
confidence, **Roadmap** holds the vessel tree as a graph, **Brain** runs a
state machine on that graph and emits `guidance` for the operator and `cmd`
for the **safety gate**, which is the only path to anything that moves.
Swapping a source adapter changes nothing below it — that is the hedge against
not knowing what the organizers supply.

- [Architecture, two views](https://claude.ai/artifact/XABPeZTARPYqgvEH36t4pr) — where it sits in the angio suite, and how a frame flows
- [System model, navigable](https://claude.ai/artifact/GkSo3vC4jKntrrYB1cZU8u) — click into any block, down to the pin map

## The model is the source of truth

`model/model.yaml` defines the blocks, the flows and the wire types.
`tools/gen_proto.py` turns it into `proto/messages.py`, which every process
imports. A field added to the model reaches both ends of the wire or neither.

```sh
make proto    # regenerate
make check    # fails if the committed proto is stale
```

## Layout

```
model/model.yaml      single source of truth: blocks, flows, types, constants
tools/gen_proto.py    model -> proto/messages.py
tools/run_demo.py     starts broker, source, eyes, brain, viewer
proto/messages.py     generated, do not edit
src/bus.py            ZeroMQ broker and Pub/Sub helpers
src/scene.py          synthetic fluoroscopy scene and the vessel graph
src/source_replay.py  L0 — publishes `frame`, synthetic or from a folder
src/eyes_stub.py      L1 — placeholder perception, replace with the model
src/brain.py          L3 — state machine on the graph
src/viewer.py         L4 — overlay, window or PNGs
firmware/             RP2040 wire driver: PIO stepping, 100 ms watchdog, pin map
docs/                 solution, stack, pitch, setup
papers/               reading list and what each paper backs
```

## Who owns what

| | |
|---|---|
| **EMB** | bus, source adapters, viewer, safety gate, firmware, bench, integration |
| **AI** | Eyes, Roadmap, Brain, datasets, training, the numbers we quote |
| **BIZ** | clinical case, market, business model, pitch, the organizer questions |

## Cut line for 24 October, 18:00

1. **replay** → Eyes → Brain → overlay and voice, on real fluoroscopy frames.
   Needs nothing from the organizers and no network.
2. **sofa** → the same chain plus the closed loop in simulation.
3. **camera** → the same chain on the tube phantom, with the wire driver.
4. **carm** → only if the organizers confirm a video feed.

Each stage stands on its own. If one fails the ones below it still run.

## Open questions, for Sebastian Schroth and Nicolas Butterwegge

1. What hardware is available on site?
2. What data is provided?
3. What are the evaluation criteria?
4. Is pre-written code, and brought hardware, allowed?
5. Is compute provided — a GPU workstation or laptop?
6. Does the ARTIS expose a documented real-time video or SDK interface, and on
   what terms?

## The gap we name rather than blur

The real training frames come from aortic arches, in silicone phantoms and
pigs. The clinical story is neurovascular, where vessel diameters are an order
of magnitude smaller, and the neuro path exists only in simulation. This is the
sharpest technical question a jury can ask. Say it before they do.
