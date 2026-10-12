# Wire driver firmware — RP2040

One degree of freedom, advance and retract. Rotation stays with the clinician.

## Pin map, Pico ↔ TMC2209 SilentStepStick

| Pico | TMC2209 | Note |
|---|---|---|
| GP2 | STEP | PIO drives this, the CPU never touches pulse timing |
| GP3 | DIR | |
| GP4 | EN | active low; high releases the driver |
| GP0 (UART0 TX) | PDN_UART | **through 1 kΩ** — single-wire UART needs the series resistor |
| GP1 (UART0 RX) | PDN_UART | direct, same node |
| GP5 | DIAG | StallGuard output, see the caveat below |
| GP6 | — | home switch, optional, pulled up |
| 3V3 | VIO | |
| GND | GND | common |
| — | VM | 12 V, **100 µF electrolytic right at the driver** |

Omitting the electrolytic on VM is the classic way to kill a TMC driver on the
first motion command. Fit it before the first power-up, not after.

## Timing

Drive wheel 20 mm, NEMA17 1.8°, 1/16 microstepping:
`π × 20 mm / 3200 = 19.635 µm` per microstep, so `period_us = 19635000 / speed_um_s`.

At the commanded ceiling of 3 mm/s that is 153 microsteps/s, a 6545 µs period.
Image resolution is 390 µm/px, so the mechanics resolve 20× finer than the
camera — the bottleneck is imaging, not the drive.

PIO runs at 1 MHz (clkdiv 125 on a 125 MHz sysclk), fixed overhead 14 µs per
iteration, so the CPU writes `y = period_us − 14`.

## Safety

- **Watchdog, 100 ms.** Enforced in the 1 kHz timer callback, not on the host.
  No valid command for 100 ticks and EN goes high, the PIO stops, a fault
  latches. The host clears the fault explicitly with flag bit 0; the firmware
  never clears it itself.
- **Rate limit** is applied here as well as on the host. A limit that exists in
  only one place is a limit that one bug removes.
- **StallGuard will most likely not work at our speed.** 153 microsteps/s is
  9.6 full steps/s, about 2.9 rpm, and StallGuard4 needs a minimum velocity to
  produce a meaningful reading. Wire DIAG anyway and measure it on the bench,
  but plan on the strain gauge: HX711 at 80 SPS is 12.5 ms per sample, so a
  stop lands within roughly 15 ms, which is 45 µm of overtravel at 3 mm/s.

## Command frame, host → Pico

10 bytes, little endian: `magic 0xA5 | ver 0x01 | seq u32 | speed i16 (µm/s) | flags u8 | crc8`.
CRC-8 poly 0x07 over the first nine bytes. The firmware echoes `seq` in its
status line, so a stalled host is visible from both ends.

Status, Pico → host, every 100 ms:
`{"seq":…,"um_s":…,"en":0|1,"fault":0|1,"wdg":…}`

## Build

```sh
export PICO_SDK_PATH=/path/to/pico-sdk
cmake -B build -S . && cmake --build build -j
# hold BOOTSEL, plug in, then copy build/driver.uf2 to the RPI-RP2 drive
```
