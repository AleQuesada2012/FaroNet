---
status: accepted
---

# Use a hysteresis comparator at the optical receiver boundary

On 2026-10-09 the team selected a conditioned detector signal followed by a
comparator with hysteresis, providing digital GPIO input without an ADC.
This replaces the parts list's ADC-based receiver approach. Hysteresis gives
separate rising/falling thresholds to reduce repeated transitions near a
noisy threshold. Under this design, software receives binary states rather
than analog sample amplitudes.

The preferred physical link is a visible-light laser with a compatible
receiver; the fallback is a matched IR emitter/phototransistor pair. TEFT4300
is a candidate for that IR fallback, not the listed 650 nm red-laser receiver.
BPW34 is a candidate visible-light detector requiring conditioning.

The exact detector/module, comparator, load/gain, thresholds, output polarity,
GPIO levels, modulation/timing, and pin map remain pending. This decision
records the interface direction, not approval of a complete circuit, a
guaranteed bitrate, or an exemption from the assignment's emitter wording.

Sources: [owner decisions](../decisions.md),
[TEFT4300 datasheet](https://www.vishay.com/docs/81549/teft4300.pdf),
[BPW34 datasheet](https://www.vishay.com/docs/81521/bpw34.pdf), and
[TI comparator hysteresis reference](https://www.ti.com/tool/TIPD144).
