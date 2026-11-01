"""Prove the perfboard layout matches the netlist and that common mistakes are caught."""

import copy

import layout
import board  # noqa: F401  (sheet.py reaches HERE through layout.board)


def rejected(label, change):
    plan = layout.make()
    change(plan)
    try:
        plan.validate()
    except AssertionError:
        return label
    raise AssertionError("validator accepted: " + label)


def swap(ref, a, b):
    def change(plan):
        part = next(p for p in plan.parts if p["ref"] == ref)
        part["pins"][a], part["pins"][b] = part["pins"][b], part["pins"][a]
    return change


def drop_link(a, b):
    def change(plan):
        plan.links = [l for l in plan.links if {l["a"], l["b"]} != {a, b}]
    return change


def add_link(a, b):
    def change(plan):
        plan.links.append({"a": a, "b": b, "net": "?", "stage": "x"})
    return change


def checks():
    plan = layout.make()
    plan.validate()
    caught = [
        rejected("D1 reversed", swap("D1", "A", "K")),
        rejected("Q1 reversed (E-B-C)", swap("Q1", "C", "E")),
        rejected("Q2 reversed", swap("Q2", "C", "E")),
        rejected("C1 reversed", swap("C1", "+", "−")),
        rejected("U1 turned 180°", swap("U1", "1 OUT1", "5 IN2+")),
        rejected("RV1 wiper and end swapped", swap("RV1", "2 cursor", "3 extremo")),
        rejected("pin 4/5 GND link missing", drop_link((12, 25), (12, 26))),
        rejected("VBIAS bus broken under U1", drop_link((14, 24), (15, 24))),
        rejected("VBIAS bus bridged to the GND row", add_link((12, 24), (13, 24))),
        rejected("Q2 emitter not grounded", drop_link((21, 29), (21, 28))),
        rejected("solder bridge U1.2 to the VBIAS bus", add_link((14, 25), (14, 26))),
        rejected("solder bridge OPT_RX to GND rail", add_link((15, 27), (15, 28))),
        rejected("GND bridges both missing",
                 lambda p: setattr(p, "wires", [w for w in p.wires if w["net"] != "GND"]
                                   ) or setattr(p, "pi", [l for l in p.pi if l["physical"] != 9])),
    ]
    # Pressing S1 must pull PANIC to GND; released it must not.
    s1 = next(p for p in plan.parts if p["ref"] == "S1")["pins"]
    pi = {l["physical"]: l["hole"] for l in plan.pi}
    released = plan.connectivity()
    assert released.root(pi[18]) != released.root(pi[6])
    pressed = plan.connectivity(extra=[(s1["1"], s1["3"])])
    assert pressed.root(pi[18]) == pressed.root(pi[6]), "pressed button must pull PANIC low"
    # Power rails stay apart.
    assert len({released.root(pi[n]) for n in (1, 2, 6)}) == 3
    return plan, caught


if __name__ == "__main__":
    plan, caught = checks()
    print("layout valid; mistakes caught:", len(caught))
    for label in caught:
        print("  -", label)
