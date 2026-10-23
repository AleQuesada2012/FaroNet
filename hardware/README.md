# Faro hardware workspace

The current team direction uses one Raspberry Pi 3 Model B rev 1.2 with
Ubuntu Server and one Raspberry Pi 2 Model B v1.1 (updated 2026-10-22), each
with a GPIO extension/header connection. The two boards share the 40-pin
header and BCM numbering, so [the breadboard guide](breadboard/README.md)
applies to both; the Pi 2's 32-bit operating system, Python environment and
network adapter still need confirmation. Visible-light laser
transmission and a matching receiver are preferred; an IR emitter/phototransistor
pair is the fallback. LDR is excluded. The inspected Pi runs Ubuntu Server
26.04.1 LTS on ARM64, kernel `7.0.0-1020-raspi`, Python 3.14.4; see
[the reported environment and GPIO permissions](pi-environment.md).
Successful SSH metadata queries identify `gpiochip0` as `pinctrl-bcm2835`.
The team accepted the official libgpiod v2 Python backend and BCM numbering;
GPIO7/8 are claimed by SPI, and GPIO7-11 remain reserved for that bus.
Python binding/line I/O tests, role assignments and receiver conditioning
remain pending. Use Python control code in
`python/src/faronet/faro/` and consult [the decisions](../docs/decisions.md).

The first iteration includes the assignment's hardware requirements, physical
panic button, TX/RX indicators, and RGB debugging LED. Separate green/yellow
debugging LEDs are omitted. LCD and speaker/buzzer belong to a later
enhancement iteration, after minimum requirements are met. The LCD will be
an aid for status/short messages; the terminal remains the chat interface.

The parts list currently names a 650 nm laser module and a BPW34 discrete
photodiode, while describing IR as primary. The latest team direction
supersedes that ordering and selects a comparator with hysteresis for digital
GPIO input, without an ADC. The detector/load circuit, comparator, thresholds,
and output levels remain unvalidated. TEFT4300 is filtered for 900-950 nm IR
and is not a suitable match for the listed red laser. Resolve the actual
emitter/detector pair. Per the owner's instruction, assume laser acceptance
for planning and keep IR as fallback if the grader rejects that substitution;
no instructor approval record has been supplied.

As the circuit is developed, keep schematic sources, a BOM with approximate
costs in colones, photographs of both board faces, and the multimeter test
record here. Record continuity, VCC/GND short checks before power, and key
voltages. Also record effective throughput and BER at three or more distances
under normal ambient light.

The final circuit must be soldered, with removable/header connections as
required by the assignment. A breadboard is for prototyping. No schematic,
component value, pin assignment, or measurement is invented by this scaffold.
