"""RV1 threshold telemetry: the Pi has no ADC, so report the comparator's decisions."""

import time

from faronet.faro.profile import LED_RX, LED_TX, TX

WINDOW_SECONDS = 0.5
BLINK_SECONDS = 1.0
SAMPLE_SECONDS = 0.002


def rx_telemetry(io, seconds: float, blink: bool, emit, clock=time.monotonic, sleep=time.sleep) -> int:
    """Sample OPT_RX, mirror it on the yellow LED and emit one report per window.

    With blink, IR and the green LED toggle every second; a reflector in front
    of D1 and Q2 then shows whether the receiver follows the emitter.
    """
    start = clock()
    next_report, next_toggle = start + WINDOW_SECONDS, start + BLINK_SECONDS
    ir = led = blink
    high = samples = edges = agree = 0
    try:
        io.set_output(TX, ir)
        io.set_output(LED_TX, ir)
        io.set_output(LED_RX, led)
        while (now := clock()) - start < seconds:
            level, new_edges = io.sample_rx()
            edges += new_edges
            if bool(level) != led:
                led = bool(level)
                io.set_output(LED_RX, led)
            high += level
            samples += 1
            agree += level == ir
            if now >= next_report:
                percent = 100 * high / samples
                report = {"t": round(now - start, 1), "rx": level, "high_pct": round(percent, 1),
                          "bar": "#" * round(percent / 10), "edges_per_s": round(edges / WINDOW_SECONDS)}
                if blink:
                    report |= {"ir": int(ir), "rx_matches_ir_pct": round(100 * agree / samples, 1)}
                emit(report)
                high = samples = edges = agree = 0
                next_report += WINDOW_SECONDS
            if blink and now >= next_toggle:
                ir = not ir
                io.set_output(TX, ir)
                io.set_output(LED_TX, ir)
                next_toggle += BLINK_SECONDS
            sleep(SAMPLE_SECONDS)
    finally:
        io.clear()
    return 0
