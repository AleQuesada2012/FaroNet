"""Check the revision-7 plan and prove known wiring mistakes are rejected.

Importing the generator builds and validates the plan; running this file also
refreshes the generated SVG/HTML/JSON outputs and the validation report.
"""
import json
import xml.etree.ElementTree as ET

import generate_layout as g


def rejects(label, change):
    plan = g.make()
    change(plan)
    try:
        plan.validate()
    except AssertionError:
        return {"mutation": label, "rejected": True}
    raise AssertionError("Validator accepted: " + label)


def swap(ref, a, b):
    """Insert a part with two terminals exchanged, as on a reversed part."""
    def change(plan):
        part = next(p for p in plan.parts if p["ref"] == ref)
        pins = part["pins"]
        pins[a], pins[b] = pins[b], pins[a]
        for pin, hole in pins.items():
            plan.nets[hole] = g.PARTS[ref]["pins"][pin]
    return change


def move(ref, pin, hole):
    def change(plan):
        part = next(p for p in plan.parts if p["ref"] == ref)
        old = part["pins"][pin]
        del plan.claims[old], plan.nets[old]
        part["pins"][pin] = hole
        plan.claim(hole, f"{ref}.{pin}", g.PARTS[ref]["pins"][pin])
    return change


def rotate_switch(plan):
    part = next(p for p in plan.parts if p["ref"] == "S1")
    part["pins"] = {"1": "e18", "2": "e20", "3": "f18", "4": "f20"}
    for pin, hole in part["pins"].items():
        plan.nets[hole] = g.PARTS["S1"]["pins"][pin]


g.export(g.LAYOUT)
L = g.LAYOUT
u1 = L.pins("U1")
results = [
    rejects("5 V joined to 3.3 V", lambda l: l.wire("T3:49", "B5:49", "5V", "power", "Injected")),
    rejects("3.3 V half-rail bridge removed",
            lambda l: setattr(l, "wires", [w for w in l.wires if w["a"] != "T3:25"])),
    rejects("Q1 inserted reversed (E-B-C)", swap("Q1", "E", "C")),
    rejects("D1 inserted reversed", swap("D1", "A", "K")),
    rejects("Q2 inserted reversed", swap("Q2", "E", "C")),
    rejects("Button rotated 90 degrees across PANIC and GND", rotate_switch),
    rejects("Button pairs bypassed by a jumper",
            lambda l: l.wire("d18", "d20", "PANIC", "panic", "Injected")),
    rejects("Trimpot wiper shorted to its grounded end",
            lambda l: l.wire("d49", "TG:30", "VTH", "rx", "Injected")),
    rejects("TX jumper one column off, in the Q1 base clip", move("R2", "1", "b57")),
    rejects("Part under a resistor body", lambda l: l.wire("b58", "TG:31", "GND", "tx", "Injected")),
    rejects("Extra jumper end on the F-J half by printed number",
            lambda l: l.wire("j30", "BG:20", "GND", "rx", "Injected")),
    rejects("U1 output shorted to GND", lambda l: l.wire("d53", "TG:32", "GND", "rx", "Injected")),
]

# Structural facts the guide states in prose.
assert L.hole_nets["PI:18"] == "PANIC" and L.hole_nets["PI:6"] == "GND"
pressed = g.UF()
pressed.p = dict(L.uf.p)
s1 = L.pins("S1")
pressed.join(s1["3"], s1["1"])
assert pressed.root("PI:18") == pressed.root("PI:6"), "Pressed button must pull PANIC low"
assert len({pressed.root(f"PI:{n}") for n in (1, 2, 6)}) == 3
assert L.pins("Q1") == {"C": "d59", "B": "d60", "E": "d61"}
assert L.pins("D1") == {"A": "h62", "K": "h63"} and L.pins("Q2") == {"E": "c62", "C": "c63"}
assert L.hole_nets[u1["1 OUT1"]] == L.hole_nets["PI:13"] == "OPT_RX"
assert L.hole_nets[u1["8 VCC"]] == "5V" and L.hole_nets["PI:11"] == "TX"
alternate = g.make("RM065")
assert alternate.pins("RV1")["2 cursor"] not in L.claims
assert {w["id"]: (w["a"], w["b"]) for w in alternate.wires} == \
    {w["id"]: (w["a"], w["b"]) for w in L.wires}
root = ET.parse(g.HERE / "faronet-breadboard.svg").getroot()
assert len([e for e in root.iter() if "data-hole" in e.attrib]) == 830
fj = sorted(h for h in L.claims if g.on_fj(h))

report = {
    "valid": True,
    "revision": g.REVISION,
    "rgb": "Removed from the design: no RGB parts, resistors or GPIO5/6/13.",
    "plan": {"parts": len(L.parts), "jumpers": len(L.wires), "holes": 830,
             "occupied_breadboard_holes": sum(not h.startswith("PI:") for h in L.claims),
             "fj_holes": fj},
    "checks": [
        "Every component terminal from circuit-reference.json placed once",
        "One terminal per hole; no occupied hole under a part body",
        "Each net continuous through clips, jumpers and S1 internal pairs",
        "No clip joins different nets; 3.3 V, 5 V and GND separate",
        "No GPIO joined to 5 V; no resistor bridged by a clip",
        "S1 open at rest, PANIC to GND when pressed",
        "RV1 terminals on three nets; RM065 wiper hole and adjustment side kept free",
        "U1.7 isolated",
        "F-J holes only at the button, under U1 and at the IR emitter",
        "D1 and Q2 on mirror rows at columns 62-63",
    ],
    "mutations": results,
    "limits": "Copper connectivity and placement rules only. No physical measurement, "
              "optical qualification or BER test.",
}
(g.HERE / "validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"valid": True, "mutations_rejected": len(results), "jumpers": len(L.wires)}))
