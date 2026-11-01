"""The revision-7 Faro on the perfboard: every lead, cable and copper link.

Rails: column 7 GND, 14 3V3, 21 GND, 28 5V. The two GND rails are joined
twice (rows 1 and 24), like the doubled rev-7a bridge on the breadboard.
D1 (rows 4-5) and Q2 (rows 21-22) point out of the right edge; their row
centres add up to 25, so a second Faro turned 180° faces emitter to
detector.
"""

from board import Layout, netlist

CHANGES = {"R6": "47 kΩ", "R10": "330 Ω", "R11": "330 Ω"}


def make() -> Layout:
    L = Layout(netlist(CHANGES))
    # 1. Rails and power from the Pi. Rail 7 GND, 14 3V3, 21 5V, 28 GND.
    L.wire("r1c7", "r1c28", "GND", "power", via=[(0.5, 7), (0.5, 28)])
    L.wire("r24c7", "r24c28", "GND", "power", via=[(24.5, 7), (24.5, 28)])
    L.lead(1, "r23c14", "power", via=[(23.55, 0), (23.55, 14)])
    L.lead(2, "r23c21", "power", via=[(23.8, 0), (23.8, 21)])
    L.lead(6, "r23c7", "power", via=[(23.3, 0), (23.3, 7)])
    L.lead(9, "r2c28", "power", via=[(1.5, 0), (1.5, 28)])
    # 2. Indicators: GPIO -> R -> LED -> GND rail 7.
    L.lead(15, "r3c1", "leds")
    L.part("R10", {"1": "r3c2", "2": "r3c5"}, "leds", covers=("r3c3", "r3c4"))
    L.part("D2", {"A": "r3c6", "K": "r3c7"}, "leds")
    L.lead(16, "r6c1", "leds")
    L.part("R11", {"1": "r6c2", "2": "r6c5"}, "leds", covers=("r6c3", "r6c4"))
    L.part("D3", {"A": "r6c6", "K": "r6c7"}, "leds")
    # 3. Panic button straddling GND rail 7.
    L.part("S1", {"1": "r10c6", "2": "r13c6", "3": "r10c8", "4": "r13c8"}, "panic",
           covers=("r10c7", "r11c7", "r12c7", "r13c7", "r11c6", "r12c6", "r11c8", "r12c8"))
    L.link("r10c6", "r10c7", "GND", "panic")
    L.part("R12", {"1": "r10c14", "2": "r10c9"}, "panic", covers=("r10c10", "r10c11", "r10c12", "r10c13"))
    L.lead(18, "r13c9", "panic", via=[(14.5, 0), (14.5, 9)])
    # 4. Emitter (rows 4-10, right edge).
    L.part("R1", {"1": "r4c21", "2": "r4c29"}, "tx", covers=tuple(f"r4c{c}" for c in range(22, 29)))
    L.link("r4c30", "r4c31", "IR_A", "tx")
    L.part("D1", {"A": "r4c32", "K": "r5c32"}, "tx")
    L.part("Q1", {"C": "r5c31", "B": "r6c31", "E": "r7c31"}, "tx")
    L.part("R3", {"1": "r6c32", "2": "r7c32"}, "tx")
    L.link("r6c31", "r6c30", "Q_BASE", "tx")
    L.part("R2", {"1": "r9c29", "2": "r6c29"}, "tx", covers=("r7c29", "r8c29"))
    L.lead(11, "r9c30", "tx", via=[(7.5, 0), (7.5, 30.5), (9, 30.5)])
    L.link("r7c31", "r7c30", "GND", "tx")
    L.link("r7c29", "r7c28", "GND", "tx")
    # 5. Receiver. U1 notch down (pin 1 bottom right), rows 12-15, columns 23 and 26.
    L.part("U1", {"5 IN2+": "r12c23", "6 IN2−": "r13c23", "7 OUT2": "r14c23", "8 VCC": "r15c23",
                  "4 GND": "r12c26", "3 IN1+": "r13c26", "2 IN1−": "r14c26", "1 OUT1": "r15c26"},
           "rx", covers=tuple(f"r{r}c{c}" for r in range(12, 16) for c in (24, 25)))
    L.link("r12c23", "r12c24", "GND", "rx")
    L.link("r12c25", "r12c26", "GND", "rx")
    L.link("r12c27", "r12c28", "GND", "rx")
    L.link("r15c22", "r15c21", "5V", "rx")
    L.part("C2", {"1": "r12c21", "2": "r12c22"}, "rx")
    L.link("r12c22", "r11c22", "GND", "power")
    L.part("C1", {"+": "r11c21", "−": "r11c22"}, "power")
    # VBIAS bus: pin 6 pad, then a bare wire down column 24 under the socket to row 23.
    L.link("r13c23", "r13c24", "VBIAS", "rx")
    for r in range(13, 23):
        L.link(f"r{r}c24", f"r{r + 1}c24", "VBIAS", "rx")
    L.wire("r16c14", "r16c22", "3V3", "rx")
    L.link("r16c22", "r17c22", "3V3", "rx")
    L.part("R5", {"1": "r16c23", "2": "r16c26"}, "rx", covers=("r16c24", "r16c25"))
    L.part("R8", {"1": "r17c23", "2": "r17c24"}, "rx")
    L.link("r15c27", "r16c27", "OPT_RX", "rx")
    L.lead(13, "r15c27", "rx", via=[(9.5, 0), (9.5, 27.5), (15, 27.5)])
    L.part("R6", {"1": "r16c27", "2": "r17c27"}, "rx")
    L.link("r17c26", "r18c26", "VTH", "rx")
    L.part("RV1", {"1 extremo": "r19c25", "2 cursor": "r18c26", "3 extremo": "r19c27"}, "rx",
           covers=("r19c26",))
    L.link("r19c27", "r19c28", "GND", "rx")
    L.wire("r13c27", "r18c27", "VTH", "rx", via=[(13, 29.5), (18, 29.5)])
    L.part("R4", {"1": "r20c25", "2": "r20c30"}, "rx", covers=("r20c26", "r20c27", "r20c28", "r20c29"))
    L.link("r20c30", "r20c31", "SENSE", "rx")
    L.wire("r14c27", "r20c31", "SENSE", "rx", via=[(14, 30.5), (20, 30.5)])
    L.part("Q2", {"C": "r20c32", "E": "r21c32"}, "rx")
    L.link("r21c31", "r21c30", "GND", "rx")
    L.link("r21c29", "r21c28", "GND", "rx")
    L.part("R9", {"1": "r22c25", "2": "r22c28"}, "rx", covers=("r22c26", "r22c27"))
    L.part("C3", {"1": "r23c25", "2": "r23c28"}, "rx", covers=("r23c26", "r23c27"))
    return L


if __name__ == "__main__":
    L = make()
    print(L.ascii())
    L.validate()
    print("valid:", len(L.parts), "parts,", len(L.wires), "cables,", len(L.links), "copper links,",
          len(L.pi), "Pi leads")
