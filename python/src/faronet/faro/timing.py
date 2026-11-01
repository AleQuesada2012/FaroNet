"""TX timing evidence for optical bring-up; records durations only, never frame content."""

import os


def _read(path: str) -> str | None:
    try:
        with open(path) as handle:
            return handle.read().strip()
    except OSError:
        return None


def system_timing() -> dict:
    """Kernel and CPU settings that bound how punctually Python can toggle GPIO."""
    cpu = "/sys/devices/system/cpu/cpu0/cpufreq/"
    return {
        "kernel": " ".join(os.uname()[2:4]),
        "sched_rt_runtime_us": _read("/proc/sys/kernel/sched_rt_runtime_us"),
        "sched_rt_period_us": _read("/proc/sys/kernel/sched_rt_period_us"),
        "timerslack_ns": _read("/proc/self/timerslack_ns"),
        "cpufreq_governor": _read(cpu + "scaling_governor"),
        "cpufreq_khz": _read(cpu + "scaling_cur_freq"),
    }


def _ms(ns: int) -> float:
    return round(ns / 1e6, 3)


class TxTiming:
    """Per-symbol lateness split into its sources, collected instead of aborting the frame.

    wake: how late the wait returned (sleep overshoot, preemption, or work done
    before the loop for symbol 0). write: the TX GPIO write. work: everything
    after the write until the next wait (LEDs, edge events, decoding).
    """

    def __init__(self, half_ns: int):
        self.half_ns = half_ns
        self.realtime = None
        self.symbols = []

    def record(self, index: int, wake_ns: int, write_ns: int, work_ns: int):
        self.symbols.append((index, wake_ns, write_ns, work_ns))

    def reset(self):
        self.symbols = []

    def summary(self, worst: int = 5) -> dict:
        if not self.symbols:
            return {"symbols": 0}
        late = sorted(wake + write for _, wake, write, _ in self.symbols)
        writes = sorted(write for _, _, write, _ in self.symbols)
        work = sorted(work for *_, work in self.symbols)

        def spread(values):
            return {"p50": _ms(values[len(values) // 2]),
                    "p99": _ms(values[(len(values) - 1) * 99 // 100]), "max": _ms(values[-1])}

        ranked = sorted(range(len(self.symbols)), reverse=True,
                        key=lambda i: self.symbols[i][1] + self.symbols[i][2])
        return {
            "symbols": len(late), "realtime": self.realtime,
            "late_ms": spread(late) | {"p90": _ms(late[(len(late) - 1) * 9 // 10])},
            "over_25pct": sum(value > self.half_ns * 0.25 for value in late),
            "over_40pct": sum(value > self.half_ns * 0.4 for value in late),
            "write_ms": spread(writes), "work_ms": spread(work),
            "worst": [{
                "symbol": self.symbols[i][0], "wake_ms": _ms(self.symbols[i][1]),
                "write_ms": _ms(self.symbols[i][2]),
                "previous_work_ms": _ms(self.symbols[i - 1][3]) if i else None,
            } for i in ranked[:worst]],
        }
