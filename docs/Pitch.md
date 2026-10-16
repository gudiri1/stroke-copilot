# Pitch — jury attacks and the answers we owe

Source: the Stroke Co-pilot plan (Story / Scenarios / Business model / Market /
Tech questions), reviewed 10 Oct 2026. This doc holds only what a jury will
attack and what we still owe as an answer.

## 0. What the brief asks, and the one sentence that answers it

The challenge, renumbered to 3 on 16 Oct, is *Autonomous Image-Guided Control
for Endovascular Procedures*. It asks for imitation learning, reinforcement
learning, a closed loop with minimal reliance on vasculature boundaries, and a
fusion of the two that keeps expert-like safety.

**One sentence:** a rule-based expert that can see the vessel graph teaches a
policy that cannot, and then stays in the room as the referee the gate compares
against.

That single mechanism answers three of their four bullets. The fourth, C-arm
auto-adjustment, we have not addressed — say so rather than implying otherwise.

**New jury question, and it is the obvious one:** *your expert is a script, not
a physician.* The answer is in their own wording, "manual **or simulated**
runs", plus the observation that distilling a privileged planner onto a student
without the privileged input is standard practice. One sentence, said before
they ask.

## 1. Contradiction to resolve before we pitch

The Scenarios page labels **D (autonomous robot, remote supervision)** as "our
hackathon demo", while T2 on the Tech-questions page concludes **"lead the demo
with the eyes, not full autonomy"**. Two pages of the same deck disagree about
what we show on 24 Oct.

**Resolved on 16 Oct by the challenge text itself.** The brief asks for learned
autonomy, so the demo is: expert closes the loop in simulation, student cloned
from its runs, both compared in a table, gate vetoing the student live. The
physical wire driver drops to a bonus, and scenario D stops being a contested
label and becomes what we are actually building.

## 2. Questions the jury will ask

**Where does "9 cases per spoke per year" come from?**
One number carries the whole revenue model (9 × €2,500 = €22,500 per spoke per
year). Currently "Flying Team estimate". Needs the publication, year and
population. If it is 4, the model does not stand up.

**You are pitching in Germany but your market is the US. Why?**
OPS 8-981.3 requires thrombectomy on site with two neuroradiologists, so remote
thrombectomy (scenario B/D) is not reimbursable in Germany today. Scenario C,
the AI co-pilot at the bedside, is legal in Germany now. Say it in that order,
in one sentence, or it sounds like we are writing off the room's home market.

**Siemens already owns Corindus/CorPath GRX, ARTIS and syngo. What is left?**
We are the perception layer on the existing X-ray stream — no new hardware, no
new room. CorPath's own failure mode, that users and beneficiaries were not the
payers, is exactly why we price per treated case to the hospital that gains the
revenue.

**What if Siemens wants exclusivity, or builds it in-house?**
Named as a threat in the canvas, still has no answer. Needs one.

**Who on your team is a clinician?**
Nobody. The mitigation is clinical advisors (AIBE/FAU, Karstensen), which today
is a plan and not a commitment. One confirmed name before 22 Oct turns this
from a hole into a partnership slide.

**Will your simulation numbers transfer?**
Our own Tech questions concede the gap (100% in sim to 30% on a real pig liver,
Pescio 2025). Pre-empt it: show the eyes on real fluoroscopy frames, not only
synthetic ones, and state the number measured on each.

**Where does the training data come from, and does it match the brain?**
It does not, and that is the sharpest question. CathAction is aortic arch,
silicone phantoms and pigs. Neuro vessels are an order of magnitude smaller and
our neuro path exists only in simulation. Name it first.

## 3. Numbers to source before 22 Oct

Each needs source, year and population, or an explicit "our estimate" label:

- 12% of eligible US stroke patients get thrombectomy
- 57.5% of Germans reach a thrombectomy centre within 30 minutes
- €43,000 lifetime cost per ischaemic stroke (Erlangen Stroke Project) —
  Erlangen is the jury's home turf, they will know the study and its year
- €9,000 (DE) / $15,000–22,000 (US) gain per case kept
- 9 cases per spoke per year (above)
- 119 German hospitals doing 5–100 thrombectomies a year
- HERMES "20 more per 100 treated"
- Stereotaxis gross margin 68% vs 15% — needs the fiscal year
- ARPA-H $36.5M over 5 years with Stryker — verify the attribution
- 148 min transfer and 58 min Flying Team

The F-numbers in the canvas point at a findings file that is not in the repo.
It belongs in `docs/Problem.md` so every slide can cite it. P11 probably closes
the interruption figure, P10 probably closes a dose figure — read before
quoting.

## 4. Inconsistencies to clean up

- The same quantity appears as "+€9,000", "−€9,053" and "about +€9,000
  (to verify)" across three pages. One figure, one label.
- Pricing is justified as "about 28% of the hospital's gain in Germany" while
  Germany is excluded as the launch market. Anchor on the US gain.
- The Channels card ends mid-sentence: "Siemens is not the reseller or legal
  manufacturer of third-party apps, so we are". Finish it. If it means we are
  the legal manufacturer, that is an MDR statement and belongs there
  deliberately, not by accident.

## 5. The table that matters more than the demo

The brief ends with "aiming for a scientific paper". That tells us what the
jury rewards: a reproducible method and an honest result, not a bigger claim.
Bring one table.

| | Success rate | Time to target | Wrong-branch events | Path length |
|---|---|---|---|---|
| Expert (sees the graph) | | | | |
| BC student (no graph) | | | | |
| BC + RL | | | | |

Over N random vessel trees, same seeds for every row, N stated. An ablation
with the gate switched off belongs beside it — that is the evidence that the
safety envelope does something measurable rather than decorative.

## 6. What the demo says that the slides cannot

Three sentences that are true because the code runs, not because we claim them:

- The frame rate is the bottleneck, not the compute: 23 ms of chain against a
  133.3 ms frame period.
- The 3 mm/s advance limit is derived, not chosen: 0.39 mm per pixel divided by
  one frame period is the fastest advance that keeps visual servoing inside one
  pixel per correction.
- The safety gate is one place with four conditions, and we can trip it live.

## 7. Framing

Every claim stays inside "research prototype, not a medical device". Nothing in
the deck may read as a claim of clinical efficacy or of an existing approval.
