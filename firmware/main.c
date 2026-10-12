/*
 * Stroke Co-pilot wire driver — RP2040 firmware.
 *
 * One degree of freedom: advance and retract. Rotation stays with the
 * clinician, which removes the hollow shaft, the collet and the slip problem,
 * and gives the shared-autonomy story its concrete form.
 *
 * The watchdog lives here and not on the host, because the host is the thing
 * most likely to stall, and a watchdog cannot be hosted by the process it is
 * supposed to catch.
 *
 * Research prototype. Not a medical device.
 */

#include <stdio.h>
#include <string.h>

#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "pico/stdlib.h"
#include "pico/time.h"

#include "step.pio.h"

/* ---- pin map, see firmware/README.md ---------------------------------- */
#define PIN_STEP 2
#define PIN_DIR 3
#define PIN_EN 4 /* TMC2209 EN is active low */
#define PIN_DIAG 5 /* StallGuard; see the caveat in the README */
#define PIN_HOME 6

/* ---- mechanics --------------------------------------------------------- */
/* 20 mm drive wheel, NEMA17 1.8 deg, TMC2209 at 1/16 microstepping:
 * pi * 20 mm / 3200 microsteps = 19.635 um per microstep.
 * period_us = 1e6 / (speed_um_s / 19.635) = 19635000 / speed_um_s          */
#define PERIOD_NUMERATOR 19635000u
#define PIO_OVERHEAD_US 14u /* fixed cycles per iteration in step.pio */
#define SPEED_MAX_UM_S 3000 /* 3 mm/s, derived in docs/Loesung.md */
#define SPEED_MIN_UM_S 20 /* below this we simply stop */

/* ---- link -------------------------------------------------------------- */
/* 10 bytes: magic, ver, seq u32 LE, speed i16 LE (um/s), flags u8, crc8.
 * i16 um/s caps at 32.767 mm/s, just under the 35 mm/s stEVE ceiling, which
 * is fine because we never command more than 3.                            */
#define FRAME_LEN 10
#define MAGIC 0xA5
#define VERSION 0x01
#define WATCHDOG_TICKS 100 /* 1 kHz loop -> 100 ms */

static PIO pio = pio0;
static uint sm;

static volatile int32_t g_speed_um_s = 0;
static volatile uint32_t g_last_seq = 0;
static volatile int32_t g_watchdog = 0; /* ticks remaining; 0 means stop */
static volatile bool g_enabled = false;
static volatile bool g_faulted = false;

static uint8_t crc8(const uint8_t *d, size_t n)
{
    uint8_t c = 0x00;
    for (size_t i = 0; i < n; i++) {
        c ^= d[i];
        for (int b = 0; b < 8; b++)
            c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x07) : (uint8_t)(c << 1);
    }
    return c;
}

static void motor_disable(void)
{
    gpio_put(PIN_EN, 1); /* active low: high releases the driver */
    pio_sm_set_enabled(pio, sm, false);
    g_enabled = false;
}

static void motor_apply(int32_t speed_um_s)
{
    int32_t mag = speed_um_s < 0 ? -speed_um_s : speed_um_s;
    if (mag > SPEED_MAX_UM_S)
        mag = SPEED_MAX_UM_S; /* the rate limit is enforced here too, not only on the host */

    if (mag < SPEED_MIN_UM_S) {
        motor_disable();
        return;
    }

    gpio_put(PIN_DIR, speed_um_s >= 0 ? 1 : 0);

    uint32_t period_us = PERIOD_NUMERATOR / (uint32_t)mag;
    uint32_t y = period_us > PIO_OVERHEAD_US ? period_us - PIO_OVERHEAD_US : 1u;

    gpio_put(PIN_EN, 0);
    if (!g_enabled) {
        pio_sm_set_enabled(pio, sm, true);
        g_enabled = true;
    }
    pio_sm_put_blocking(pio, sm, y);
}

/* 1 kHz control loop. The only place that decides whether the motor may run. */
static bool tick(repeating_timer_t *t)
{
    (void)t;

    if (gpio_get(PIN_DIAG)) { /* StallGuard, if it is usable at this speed */
        g_faulted = true;
        g_speed_um_s = 0;
    }

    if (g_watchdog > 0) {
        g_watchdog--;
        if (g_watchdog == 0) {
            g_faulted = true;
            g_speed_um_s = 0;
        }
    }

    motor_apply(g_faulted ? 0 : g_speed_um_s);
    return true;
}

static void handle_frame(const uint8_t *f)
{
    if (f[0] != MAGIC || f[1] != VERSION)
        return;
    if (crc8(f, FRAME_LEN - 1) != f[FRAME_LEN - 1])
        return;

    uint32_t seq = (uint32_t)f[2] | ((uint32_t)f[3] << 8) | ((uint32_t)f[4] << 16)
                 | ((uint32_t)f[5] << 24);
    int16_t speed = (int16_t)((uint16_t)f[6] | ((uint16_t)f[7] << 8));
    uint8_t flags = f[8];

    if (flags & 0x01) { /* host clears a fault explicitly; we never self-clear */
        g_faulted = false;
    }

    g_last_seq = seq;
    g_speed_um_s = speed;
    g_watchdog = WATCHDOG_TICKS;
}

int main(void)
{
    stdio_init_all();

    gpio_init(PIN_DIR);
    gpio_set_dir(PIN_DIR, GPIO_OUT);
    gpio_init(PIN_EN);
    gpio_set_dir(PIN_EN, GPIO_OUT);
    gpio_put(PIN_EN, 1); /* released until a valid command arrives */
    gpio_init(PIN_DIAG);
    gpio_set_dir(PIN_DIAG, GPIO_IN);
    gpio_pull_down(PIN_DIAG);
    gpio_init(PIN_HOME);
    gpio_set_dir(PIN_HOME, GPIO_IN);
    gpio_pull_up(PIN_HOME);

    uint offset = pio_add_program(pio, &step_program);
    sm = pio_claim_unused_sm(pio, true);
    step_program_init(pio, sm, offset, PIN_STEP);

    repeating_timer_t timer;
    add_repeating_timer_ms(-1, tick, NULL, &timer); /* negative: 1 ms between starts */

    uint8_t buf[FRAME_LEN];
    size_t have = 0;
    absolute_time_t next_status = make_timeout_time_ms(100);

    for (;;) {
        int c = getchar_timeout_us(0);
        while (c != PICO_ERROR_TIMEOUT) {
            if (have == 0 && (uint8_t)c != MAGIC) {
                c = getchar_timeout_us(0); /* resync on the magic byte */
                continue;
            }
            buf[have++] = (uint8_t)c;
            if (have == FRAME_LEN) {
                handle_frame(buf);
                have = 0;
            }
            c = getchar_timeout_us(0);
        }

        if (absolute_time_diff_us(get_absolute_time(), next_status) <= 0) {
            printf("{\"seq\":%lu,\"um_s\":%ld,\"en\":%d,\"fault\":%d,\"wdg\":%ld}\n",
                   (unsigned long)g_last_seq, (long)g_speed_um_s, g_enabled ? 1 : 0,
                   g_faulted ? 1 : 0, (long)g_watchdog);
            next_status = make_timeout_time_ms(100);
        }
        tight_loop_contents();
    }
}
