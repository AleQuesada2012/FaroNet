# Faro hardware workspace

Current Oct 25 instructions: use [the revision-6 breadboard guide](breadboard/README.md)
and its HTML/SVGs for all pin and polarity decisions; its common-cathode
active-high RGB supersedes the older LS125 HTML branch. A uses Ubuntu on
Pi 3 (direct image/balenaEtcher, 5 V/2.5 A supply); B uses PiOS on Pi 2
(Raspberry Pi Imager). The circuit is assembled but disconnected from A's
Pi until the Oct 26 meeting. Software setup/metadata checks are recorded in
[the updated Pi profile](pi-environment.md), and the runnable physical-test
sequence is in [the optical guide](../docs/optical-bringup.md). The older
planning notes below are not physical qualification evidence.

The current team direction uses one Raspberry Pi 3 Model B rev 1.2 with
Ubuntu Server and one Raspberry Pi 2 Model B v1.1 (updated 2026-10-22), each
with a GPIO extension/header connection. The two boards share the 40-pin
header and BCM numbering, so [the breadboard guide](breadboard/README.md)
applies to both; the Pi 2 now runs PiOS, with its exact Python environment
and network adapter still to check. Visible-light laser
transmission and a matching receiver are preferred; an IR emitter/phototransistor
pair is the fallback. LDR is excluded. The inspected Pi runs Ubuntu Server
26.04.1 LTS on ARM64, kernel `7.0.0-1020-raspi`, Python 3.14.4; see
[the reported environment and GPIO permissions](pi-environment.md).
Successful SSH metadata queries identify `gpiochip0` as `pinctrl-bcm2835`.
The team accepted the official libgpiod v2 Python backend and BCM numbering;
GPIO7/8 are claimed by SPI, and GPIO7-11 remain reserved for that bus.
A's Python binding is installed, metadata checked, and role assignments
follow the current breadboard profile. Physical line I/O and receiver
conditioning remain unverified. Use Python control code in
`python/src/faronet/faro/` and consult [the decisions](../docs/decisions.md).

Both current breadboard plans include the physical panic button and TX/RX
indicators. The RGB plan adds an optional debugging LED; the basic Faro
works without it. Software defaults to basic, and `--rgb` enables the RGB
pins locally, including in metadata preflight. Debugging patterns remain
provisional and are independent of optical communication. LCD and speaker/buzzer belong to a later
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
