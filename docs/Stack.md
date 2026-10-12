# Stack — Beschaffung, Repos, Setup

Ausgangslage 12.10.: nichts vorhanden, 9 Tage bis zum Event.

## 1. Beschaffung, ca. 205 €

Richtwerte, beim Bestellen prüfen. Amazon/Reichelt/Conrad, 1–2 Tage.

### Wire-Driver, 1 DoF (ca. 75 €)
NEMA17 1,8° 42×40 (12) · TMC2209 SilentStepStick (8) · Raspberry Pi Pico (5) ·
Netzteil 12 V/2 A + Buchse (12) · 2× GT2-Zahnrad 20T + O-Ringe als
Friktionsbelag (8) · Druckfeder + M3-Sortiment (10) · Steckbrett, Jumper,
**100 µF Elko** (10) · Federstahl-/Nitinoldraht Ø 0,4–0,9 mm aus dem Modellbau
(10) — **kein echter Führungsdraht**, der ist Medizinprodukt und für den Bench
unnötig.

### Kamera-Bench (ca. 85 €)
USB-Webcam mit Manuell-/Makrofokus (40) · LED-Flächenleuchte für Durchlicht
(20) · Stativ/Klemme (15).

Rolling Shutter genügt: bei 3 mm/s und 1/60 s Belichtung bewegt sich der Draht
0,05 mm = **0,13 px** bei 0,39 mm/px. Global Shutter wäre weggeworfenes Geld.

### Phantom ohne 3D-Drucker (ca. 45 €)
Klarer PVC-/Silikonschlauch Ø 4–6 mm innen, 2 m (8) · Y- und T-Verbinder (8) ·
flache Acrylbox ~20×15×5 cm (12) · Heißkleber, Kabelbinder (7) ·
Glycerin 99,5 % 2 L (25) **erst bei Bedarf**.

Upgrade-Pfad, kostet nur eine Mail: FabLab Erlangen bzw. FAU-Drucker für ein
Klarresin-Phantom.

## 2. Software

### SOFA — Versionsfalle, früh starten
Die stEVE-README warnt: in **SOFA v23.12 hat sich das BeamAdapter-Interface
geändert, die Anpassung steht aus**. Entweder Binaries **≤ v23.06** (gebunden
an **Python 3.8**) oder Quellbau:

```sh
git clone -b v23.12.00 --depth 1 https://github.com/sofa-framework/sofa.git ./src
# numpy scipy pybind11 ins Ziel-venv, dann cmake u.a. mit:
#   -D SOFA_FETCH_SOFAPYTHON3=True
#   -D SOFA_FETCH_BEAMADAPTER=True
cd build && make -j && make install
export SOFA_ROOT=<install-prefix>
export PYTHONPATH=$SOFA_ROOT/plugins/SofaPython3/lib/python3/site-packages
```

**Im Docker-Container bauen** (ubuntu:22.04): ein fehlgeschlagener Build
zerlegt sonst das System-Python. Zeitbudget 4–8 h, stark streuend.

### stEVE (MIT)
`lkarstensen/stEVE`, `/stEVE_bench`, `/stEVE_training`.
```sh
python3 -m pip install -e .
python3 examples/function_check.py
```
Env-API: `reset()`, `step(action)`, `render()`, `close()`.
Beobachtung: aktuelle und vorige Spitzenposition als je drei Punkte im Abstand
2 mm in 2D-Bildkoordinaten, plus Ziel und letzte Aktion, normiert auf [−1, 1].
Aktion: translatorische und rotatorische Geschwindigkeit je Gerät, Grenzen
35 mm/s und 3,14 rad/s.
Umgebungen: BasicWireNav (VMR #0011_H_AO_H), ArchVariety, **DualDeviceNav**
(Aorta aus CTA + Hirngefäße aus MRA — unser Neuro-Pfad).

### Daten
**CathAction** — airvlab.github.io/cathdata/, Spiegel `airvlab/CathAction` auf
HuggingFace. 569 Videos, 500 000+ annotierte Frames, ~25 000 Masken, Katheter
und Draht getrennt, Spitzen-Boxen mit collision/normal, 5 Aktionsklassen.
Fünf Silikon-Aortenbögen, fünf Schweine. Keine Patientendaten. Lizenz offen.
Baselines Dice/IoU: UNet 51,69/57,51 · TransUNet 56,52/55,93 ·
SwinUNet 61,26/59,54 · SSL 56,95/56,87 · SegViT 63,47/54,12.

**Vascular Model Repository** — vascularmodel.com.

## 3. Compute

Entscheidungsregel:

1. Hat jemand im Team eine NVIDIA-GPU im Laptop → das wird die Demo-Kiste,
   TensorRT, nichts kaufen.
2. Sonst CPU-Inferenz mit einem mobile-class Netz. Richtwerte, zu messen:
   MobileNetV3-small-Encoder-U-Net @512² grob 2–3 GFLOPs; 8-Kern-AVX2 über
   oneDNN 30–60 GFLOPS effektiv → 3/40 = **75 ms**, im 133-ms-Budget ohne
   Reserve. Mit int8 über ONNX Runtime → **25–40 ms**.
3. Keine GPU im ganzen Team: Jetson Orin Nano Super, ca. 270 €. Beantwortet
   **T3 („edge inference at the spoke vs cloud") mit Hardware statt mit einer
   Folie.** Kostet 6–10 h für JetPack und PyTorch-Wheels.

Training auf Colab/Kaggle T4, kostenlos.

**Nicht auf 256×256 runterskalieren.** Ein 0,014"-Neurodraht misst 0,356 mm und
ist bei 0,39 mm/px bereits unter 1 px breit. Auf unserem Bench mit 0,4–0,9 mm
Draht in Nahaufnahme unkritisch, aber der Punkt gehört in den Pitch.

## 4. Reihenfolge bis 21.10.

| Tag | EMB | AI |
|---|---|---|
| Mo 12. | Bestellung raus (1 h), SOFA-Build im Docker starten (4–8 h) | CathAction ziehen, Lizenz klären |
| Di 13.–Mi 14. | **ZMQ-Backbone** steht bereits im Repo: gegen echte Clips testen | Baseline-Training |
| Do 16.–Fr 17. | stEVE BasicWireNav läuft, `sofa`-Adapter auf denselben Contract (4–6 h) | erstes Modell, **Spitzenfehler in mm** |
| Sa 18.–So 19. | Wire-Driver bauen, Firmware flashen, Safety gate (10 h), Phantom (2 h) | Modell auf Bench-Bilder nachziehen |
| Mo 20.–Di 21. | Kamera-Bench, px/mm-Kalibrierung, kompletter Trockenlauf (6 h) | |

Vorrang wenn es kippt: `replay` + Eyes + Brain + Overlay. **Die Schnittlinie
braucht weder SOFA noch einen Aktor.**
