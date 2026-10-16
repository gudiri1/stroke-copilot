# Stroke Co-pilot

Robotics & AI Hackathon 2026, Siemens Healthineers Innovation Center Erlangen,
22–24 October. Challenge 3, *Autonomous Image-Guided Control for Endovascular
Procedures*.

Autonomous guidewire navigation, learned from a privileged expert and kept
inside a safety envelope. A rule-based planner that can see the vessel graph
demonstrates. A policy that cannot see it is cloned from those runs and then
improved by reinforcement learning. A gate compares the two on every frame and
is the only path to the motor.

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
[   8] view is ambiguous at BIF1: separation 0.00 -> 0.54 at alpha -70 beta +40
[   8] bifurcation_ahead  ACCESS -> BIF1   46.4 px  conf 0.76
[   8] view  -> alpha -70  beta +40  score 0.70  (ambiguous_bifurcation)
[  16] wrong_branch       BIF1 -> LEFT    77.3 px  conf 0.88
[  79] target_reached     RIGHT -> TARGET  17.6 px  conf 0.81
[  83] handover — conf 0.00
```

Read the first three lines together: from the frontal view the two branches at
`BIF1` project onto the same pixels, so the planner asks for an angle where
they do not, the gate lets the gantry move because the wire is standing still,
and the wrong turn at line four is visible only because the view changed. That
is what "auto-adjust the C-arm" buys — not a nicer picture, but a decision that
can be made at all.

Overlay frames land in `out/`. With a display, `src/viewer.py` opens a window
instead.

## What the challenge asks, and what answers it

| The brief | Our answer |
|---|---|
| Clone expert navigation from **manual or simulated** runs | The rule-based planner is the simulated expert; its episodes are the demonstrations |
| Let the policy self-play in simulation | stEVE on SOFA, the endovascular RL environment from FAU |
| Navigate with **minimal reliance on vasculature boundaries** | The expert sees the vessel graph. The student never does — which is why it must be able to move the camera |
| Fuse RL and IL, **keeping expert-like safety** | The gate compares student against expert every frame and vetoes beyond a bound |
| Auto-adjust the C-arm | 703 candidate angles scored per bifurcation; the gate releases the move only while the wire is still |
| Aiming for a scientific paper | The evaluation table, not the demo, is the deliverable for that |

The expert never leaves the room. It stops driving and becomes the referee.

## The architecture in one paragraph

Four interchangeable image sources publish one `frame` contract. Everything
downstream is fixed: **Eyes** segments the wire and reports a tip with a
confidence, **Roadmap** holds the vessel tree as a graph, and **Brain** holds
two policies — a rule-based **expert** with the graph and a learned **student**
without it. Both emit `cmd`, and the expert also emits `view` when the branch
ahead is unreadable from the current angle. The **safety gate** decides what
reaches the two actuators, the wire driver and the gantry, and it is the only
path to either. Swapping a source adapter changes nothing below it — the hedge
against not knowing what the organizers supply.

## Trip the gate

Six conditions that cannot be demonstrated are a slide, not an argument. With
the demo running, `tools/fault.py` plays a misbehaving student on the same
topics the real policies use:

```sh
make demo &
python3 tools/fault.py deviation    # [  21] VETO cmd  +4.00 mm/s — deviation 4.00 mm/s
python3 tools/fault.py rate         # [  50] CLAMP cmd +4.40 -> +3.00 mm/s — rate limit
python3 tools/fault.py interlock    # [  75] VETO view -70/+40 — wire is moving at 3.00 mm/s
```

There is no path around the gate, which is why injecting a command from
outside the system changes nothing about who is allowed to move.

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

1. **Expert closes the loop.** replay or the synthetic scene → Eyes → expert →
   gate → overlay. Needs nothing from the organizers and no network.
2. **Demonstrations and cloning.** The expert drives in simulation, episodes are
   recorded, the student is cloned. Behavioural cloning trains in minutes on a
   CPU, so this stage survives having no GPU.
3. **The evaluation table.** Expert vs student on success rate, time to target,
   wrong-branch events and path length, over N random vessel trees.
4. **RL fine-tuning.** Only with a GPU. stEVE reports 6h39min for one run.
5. **Physical bench.** Tube phantom, camera, wire driver — the evidence that it
   transfers off synthetic images.
6. **carm** → only if the organizers confirm a video feed.

Each stage stands on its own. If one fails the ones below it still run, and
stages 1 to 3 together already answer three of the four bullets.

## Open questions, for Sebastian Schroth and Nicolas Butterwegge

1. What hardware is available on site?
2. What data is provided?
3. What are the evaluation criteria?
4. Is pre-written code, and brought hardware, allowed?
5. Is compute provided — a GPU workstation or laptop? **Now decisive:** the
   brief asks for reinforcement learning, and RL without a GPU is not a
   three-day exercise.
6. Does the ARTIS expose a documented real-time video or SDK interface, and on
   what terms?

## The gap we name rather than blur

The real training frames come from aortic arches, in silicone phantoms and
pigs. The clinical story is neurovascular, where vessel diameters are an order
of magnitude smaller, and the neuro path exists only in simulation. This is the
sharpest technical question a jury can ask. Say it before they do.

Second: **our expert is a script, not a physician.** The brief says "manual or
simulated runs", so a scripted expert is in scope, and distilling a privileged
planner onto a student that lacks the privileged input is an established
method. Say that in one sentence rather than letting it be found.
