# Lösung — Systemarchitektur

Technische Seite. Code, Topics, Dateinamen, Variablen: Englisch.

## 0. Leitentscheidung

Zwei Entscheidungen, und die zweite ist am 16.10. gefallen, als die
Challenge-Beschreibung konkret wurde.

**SOFA ist die Anlage (plant), nicht die Kamera.**

SOFA + BeamAdapter liefert Draht-Physik, Closed Loop und einen reproduzierbaren
Benchmark. Die Perception wird auf **echten** Fluoroskopie-Frames trainiert und
gemessen (CathAction). SOFA-Renderings werden nicht als Trainingsbilder benutzt.
Grund: Pescio 2025 — 100 % in Simulation, 30 % an der echten Schweineleber. Die
Lücke liegt in der Bildgebung, nicht in der Physik.

**Der Experte fährt vor, der Student fährt nach, das Gate entscheidet.**

Die Challenge verlangt Imitation Learning, RL und die Fusion aus beidem mit
„expert-like safety". Unsere frühere Entscheidung — kein gelerntes Netz auf dem
kritischen Pfad — war damit gegen die Aufgabe. **Korrigiert:** nicht die Policy
weglassen, sondern sie einrahmen.

- Der **Experte** ist der regelbasierte Planer. Er kennt den Gefäßgraphen und
  den Zielpfad. Das ist privilegierte Information, die ein echtes System nicht
  hat. Er erzeugt die Demonstrationen.
- Der **Student** wird darauf geklont und bekommt den Graphen **nie**. Genau das
  heißt „minimal reliance on vasculature boundaries" in der Praxis.
- RL verbessert den Student über den Experten hinaus.
- Das **Gate** vergleicht in jedem Frame den Befehl des Students mit dem, was
  der Experte getan hätte, und vetot jenseits einer Schranke. Der Experte hört
  auf zu fahren und wird zum Schiedsrichter.

Ein Mechanismus, drei ihrer vier Punkte. Verworfen: reines RL from scratch
(ohne GPU in drei Tagen nicht zu zeigen) und reines BC (lernt per Definition
nichts Neues, ihr Punkt „let it get better on its own" bliebe offen).

**Der Angriffspunkt, den wir selbst benennen:** unser Experte ist ein Skript,
kein Arzt. Die Antwort steht in ihrem eigenen Text — „manual **or simulated**
runs" — und Privileged-Expert-Distillation ist ein etabliertes Verfahren, kein
Notbehelf.

## 1. Ebenen

```
L0  Source adapter      -> topic "frame"     sofa | replay | camera | carm
L1  Perception "Eyes"   -> topic "tip"       Segmentierung, Spitze, Confidence
L2  Roadmap                                  Gefäßgraph + 2D-2D-Registrierung
L3  "Brain"             -> topic "guidance"  Zustandsautomat auf dem Graphen
L4  Output                                   Overlay, Voice, optional "cmd"
L5  Safety gate                              Confidence, Watchdog, Kraft, Handover
```

Jede L0-Quelle erfüllt denselben Frame-Contract. Taucht am 22.10. Hardware auf,
wird nur der Adapter getauscht, L1–L5 bleiben unberührt.

## 2. Message-Contracts

Transport: ZeroMQ PUB/SUB über `ipc://`, Payload msgpack, Frame-Bytes als
zweiter Part. Broker (XSUB/XPUB) in `src/bus.py`, damit Nodes in beliebiger
Reihenfolge starten.

**Verworfen: ROS 2 als Kern** — DDS-Discovery und colcon in einem fremden Netz
mit zwei Technikern ist ein Tag-1-Risiko. ROS 2 nur als Bridge-Node, falls ein
gestellter Roboter das spricht.

Die Typen stehen in `model/model.yaml` und werden nach `proto/messages.py`
generiert. `seq` läuft durch alle Topics: jede Ausgabe ist auf ihren Frame
rückführbar, die Stufenlatenz ohne Extra-Instrumentierung messbar.

## 3. Zeit- und Datenbudget

Annahmen, am Tag 1 zu messen: 512×512 mono8, Detektor-FOV 200 mm →
**0,39 mm/px**. Bildrate 7,5 Hz (stEVE arbeitet mit 7,5 Hz; entspricht
gepulster Neuro-Fluoroskopie). Frameperiode = 1000/7,5 = **133,3 ms**.

| Stufe | ms |
|---|---|
| Grab + Decode | 3 |
| Preprocess | 2 |
| Inferenz U-Net-small FP16 TensorRT @512² | 8 |
| Postprocess | 4 |
| Graph-Logik | 1 |
| Overlay + Present | 5 |
| **Summe** | **23** |

Reserve 110,3 ms. Engpass ist die Bildrate, nicht die GPU.
Glass-to-glass: 133,3 + 23 + 16,7 = **173 ms**.

Datenrate: 512×512×1 B = 256 KiB/Frame, ×7,5 = **1,92 MiB/s**. Bei 1024²
mono16 @15 Hz: **252 Mbit/s** — über `ipc://` problemlos, über Event-WLAN
nicht. → Alles auf einer Kiste.

**Abgeleitete Vorschubgrenze:** 0,39 mm / 0,1333 s = **2,9 mm/s**, im Demo auf
3 mm/s begrenzt. stEVE erlaubt 35 mm/s, das ist offene Steuerung, nicht
bildgeführte Korrektur.

Voice: Phrasenbank beim Start als WAV vorgerendert, 512 Frames @ 48 kHz =
**10,7 ms**. Verworfen: Live-TTS im kritischen Pfad.

## 4. Einsatzsicht und Hub-Strecke

Patient, Tisch, Röntgenröhre, Detektor, Angio-Anlage, Monitor und Arzt
existieren bereits. Das Produkt ist eine Box am Videoausgang.

- **16,1 Mbit/s** roh bei 512² mono8 @7,5 Hz; **62,9 Mbit/s** bei 1024².
- **+60–110 ms** einseitig: Encode 20–40, Glasfaser innerdeutsch 5–15,
  Decode 20–40, Display 17. Schätzung, zu messen.
- Das Budget trägt **Beratung, keine Fernsteuerung eines Roboters.**

Zwei Dinge laut sagen: diagnosetaugliche Kompression von Fluoroskopie ist eine
Zulassungsfrage, kein Codec-Parameter. Und OPS 8-981.3 verlangt die
Thrombektomie vor Ort mit zwei Neuroradiologen — in Deutschland ist die
Strecke Fernberatung mit lokalem Operateur (Szenario C), nicht Fernbehandlung.
Das ist der Grund für US-first.

**Schwächstes Glied:** der Pfeil „video out" von der ARTIS. An einer klinischen
Anlage ist ein Echtzeit-Stream eine Herstellerschnittstelle, keine Buchse.
Offene Frage 6 an die Veranstalter. Der Prototyp braucht sie nicht.

## 5. Hardware

**Phantom.** Klarer PVC-Schlauch mit Y-Verbindern in einer flachen Acrylbox.
Wir brauchen keine Anatomie, wir brauchen Bifurkationen — genau die Topologie,
auf der L3 arbeitet. Im Pitch als Topologie-Prüfstand benennen. Glycerin
(n ≈ 1,47 gegen Klarresin n ≈ 1,49) erst, wenn der Draht bei Durchlicht nicht
als Silhouette durchkommt; stEVE braucht die Immersion, weil dort ein
gedrucktes Phantom mit dicken Wänden steht.

**Wire-Driver, 1 DoF.** Nur Vorschub. Rotation bleibt beim Menschen — halbiert
die Mechanik und ist die Shared-Autonomy-Geschichte, die T4 beantwortet.

NEMA17 1,8° = 200 Vollschritte/U, TMC2209 bei 1/16 → 3200 µSchritte/U.
Treibrad Ø 20 mm → 62,83/3200 = **19,6 µm pro µSchritt**. Gegen 390 µm/px:
die Mechanik ist **20× feiner** als das, was die Kamera auflöst.

RP2040, Schrittgenerierung in PIO, Regelschleife 1 kHz, Watchdog 100 ms **in
der Firmware** — der Host ist das, was am wahrscheinlichsten hängen bleibt.

**Korrektur:** StallGuard trägt bei 153 µSchritten/s (≈ 2,9 U/min)
höchstwahrscheinlich nicht, StallGuard4 braucht eine Mindestdrehzahl. Der
HX711 mit Dehnungsmessstreifen bleibt: 80 SPS = 12,5 ms/Sample, Stopp in
≈ 15 ms, bei 3 mm/s **45 µm Überfahrweg**.

## 6. Schnittlinie für den 24.10., 18:00

1. **Experte schließt den Kreis.** `replay` oder synthetische Szene → Eyes →
   Experte → Gate → Overlay. Ohne Veranstalter-Hardware, ohne Netz.
2. **Demonstrationen und Klonen.** Experte fährt in Simulation, Episoden werden
   aufgezeichnet, Student wird geklont. BC trainiert in Minuten auf CPU — diese
   Stufe überlebt also, dass wir keine GPU haben.
3. **Die Evaluationstabelle.** Experte gegen Student: Erfolgsrate, Zeit bis
   Ziel, Falschast-Ereignisse, Pfadlänge, über N zufällige Gefäßbäume.
4. **RL-Feintuning.** Nur mit GPU. stEVE nennt 6 h 39 min für einen Lauf.
5. **Physischer Bench.** Phantom, Kamera, Wire-Driver — der Beleg, dass es
   synthetische Bilder verlässt.
6. `carm`, nur falls T1 positiv.

Stufen 1 bis 3 beantworten zusammen schon drei der vier Punkte. Der
Wire-Driver ist damit von Pflicht auf Zugabe gerutscht.

## 7. Bekannte Lücken

- **CathAction ist Aorta und Schwein, unsere Geschichte ist Neuro.**
  Gefäßdurchmesser unterscheiden sich um eine Größenordnung. Härtester
  technischer Angriffspunkt. Benennen, nicht kaschieren.
- Segmentierungs-Baselines auf CathAction: Dice 51,69 (UNet) bis 63,47
  (SegViT). Ein dünner Draht bestraft Dice hart. → **Spitzenfehler in mm
  pitchen, nicht Dice.**
- 2D-2D- statt 3D-2D-Registrierung. Q4 ist in drei Tagen nicht zu lösen.
- Lizenz von stEVE geklärt (MIT); Download- und Lizenzlage von CathAction
  noch nicht.
- **Unser Experte ist ein Skript, kein Arzt.** Siehe Abschnitt 0.
- **C-Arm-Verstellung fehlt ganz.** In Simulation ist der Projektionswinkel ein
  Kameraparameter und damit billig nachrüstbar. Entscheidung am Event, nicht
  vorher.

## 8. Quellen

- stEVE: Karstensen et al., arXiv:2410.01956, Computers in Biology and
  Medicine 2025. `lkarstensen/stEVE`, `/stEVE_bench`, `/stEVE_training`.
  SOFA + BeamAdapter, 7,5 Hz, 35 mm/s und 3,14 rad/s.
- CathAction: Jianu et al., arXiv:2408.13126. 569 Videos, 500 000+ annotierte
  Frames, ~25 000 Masken, fünf Silikon-Aortenbögen und fünf Schweine.
- Vascular Model Repository: vascularmodel.com
