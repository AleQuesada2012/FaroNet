"""Capture the peer Faro's RX edges and measure why its frames fail to decode.

Run on the receiving Faro (outputs untouched), then start a frame on the other
one, for example `optical-loopback --count 1`. The longest burst of edges is
taken as the frame and compared with an ideal Manchester clock:

- clock_ppm: the sender's half-bit as measured by this Pi's clock.
- high_widening_ms: how much longer each light pulse is than the dark ones.
- max_offset_half_bits: worst edge offset against the nominal clock the
  decoder uses (it samples mid-half-bit, so 0.5 or more breaks the frame).

    sudo .venv/bin/python tools/capture_edges.py --half-bit-ms 10 --seconds 40
"""

import argparse
import json
import time


def analyze(edges, half_ns):
    """edges: [(timestamp_ns, level)] with the level after each edge."""
    bursts, current = [], []
    for edge in edges:
        if current and edge[0] - current[-1][0] > 4 * half_ns:
            bursts.append(current)
            current = []
        current.append(edge)
    if current:
        bursts.append(current)
    if not bursts:
        return {"edges": 0, "frame_found": False}
    burst = max(bursts, key=len)
    if len(burst) < 32:
        return {"edges": len(edges), "frame_found": False, "longest_burst_edges": len(burst)}
    slots, odd = [0], 0
    for (a, _), (b, _) in zip(burst, burst[1:]):
        units = round((b - a) / half_ns)
        odd += units not in (1, 2)
        slots.append(slots[-1] + max(units, 1))
    times = [t for t, _ in burst]
    n = len(times)
    mean_s, mean_t = sum(slots) / n, sum(times) / n
    var = sum((s - mean_s) ** 2 for s in slots)
    slope = sum((s - mean_s) * (t - mean_t) for s, t in zip(slots, times)) / var
    base = mean_t - slope * mean_s
    fit = [t - (base + slope * s) for s, t in zip(slots, times)]
    rise = [r for r, (_, level) in zip(fit, burst) if level == 1]
    fall = [r for r, (_, level) in zip(fit, burst) if level == 0]
    # The decoder anchors on the first rising edge and counts nominal half-bits from it.
    anchor = next(t - s * half_ns for (t, level), s in zip(burst, slots) if level == 1)
    nominal = [t - (anchor + s * half_ns) for s, t in zip(slots, times)]
    return {
        "frame_found": True,
        "edges": len(edges),
        "frame_edges": n,
        "frame_half_bits": slots[-1],
        "odd_intervals": odd,
        "clock_ppm": round((slope / half_ns - 1) * 1e6, 1),
        "high_widening_ms": round((sum(fall) / len(fall) - sum(rise) / len(rise)) / 1e6, 3),
        "fit_jitter_max_ms": round(max(abs(r) for r in fit) / 1e6, 3),
        "max_offset_half_bits": round(max(abs(r) for r in nominal) / half_ns, 3),
        "end_offset_half_bits": round(nominal[-1] / half_ns, 3),
    }


def capture(chip, seconds):
    import gpiod
    from gpiod.line import Clock, Direction, Edge

    from faronet.faro.profile import RX

    settings = gpiod.LineSettings(direction=Direction.INPUT, edge_detection=Edge.BOTH,
                                  event_clock=Clock.MONOTONIC)
    edges, gaps, last = [], 0, None
    with gpiod.request_lines(chip, consumer="faronet-edge-capture", config={RX: settings},
                             event_buffer_size=4096) as request:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if not request.wait_edge_events(0.05):
                continue
            for event in request.read_edge_events(max_events=512):
                gaps += last is not None and event.global_seqno != last + 1
                last = event.global_seqno
                edges.append((event.timestamp_ns, int(event.event_type == event.Type.RISING_EDGE)))
    return edges, gaps


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chip", default="/dev/gpiochip0")
    parser.add_argument("--half-bit-ms", type=float, default=10)
    parser.add_argument("--seconds", type=float, default=40)
    args = parser.parse_args()
    print(json.dumps({"capturing_seconds": args.seconds}), flush=True)
    edges, gaps = capture(args.chip, args.seconds)
    print(json.dumps(analyze(edges, round(args.half_bit_ms * 1e6)) | {"seq_gaps": gaps}, sort_keys=True))


if __name__ == "__main__":
    main()
