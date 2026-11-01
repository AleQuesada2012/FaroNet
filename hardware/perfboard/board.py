"""Hole model of the team's 7 x 9 cm blue perfboard, and a layout checker.

Component-side coordinates: column 1-32 as printed on the bare side,
row 1-24 counted from the printed-number edge (the 12 large holes are past
row 24). The copper side is the same grid flipped top-to-bottom, so column
numbers read left to right on both sides.

Copper, measured from the owner's photos (2026-10-31):
- columns 7, 14, 21 and 28 are rails: one strip joining all 24 rows;
- every other column belongs to a horizontal two-hole pair in its row:
  (1,2) (3,4) (5,6) | (8,9) (10,11) (12,13) | (15,16) (17,18) (19,20) |
  (22,23) (24,25) (26,27) | (29,30) (31,32).
The single square pads at both edges and the 12 large holes are not used.
"""

from collections import defaultdict
import json
from pathlib import Path

ROWS, COLS = 24, 32
RAILS = (7, 14, 21, 28)
PAIRS = ((1, 2), (3, 4), (5, 6), (8, 9), (10, 11), (12, 13), (15, 16), (17, 18),
         (19, 20), (22, 23), (24, 25), (26, 27), (29, 30), (31, 32))
PAIR_OF = {c: pair for pair in PAIRS for c in pair}
HERE = Path(__file__).resolve().parent
CANON = json.loads((HERE.parent / "breadboard" / "circuit-reference.json").read_text())


def hole(text: str) -> tuple[int, int]:
    """'F12C30' style is avoided; holes are written 'r12c30' in this file."""
    row, col = text[1:].split("c")
    r, c = int(row), int(col)
    assert 1 <= r <= ROWS and 1 <= c <= COLS, text
    return r, c


def name(h: tuple[int, int]) -> str:
    return f"F{h[0]}·C{h[1]}"


def conductor(h: tuple[int, int]) -> str:
    """The copper piece a hole belongs to."""
    r, c = h
    if c in RAILS:
        return f"rail{c}"
    return f"pair{r}:{PAIR_OF[c][0]}"


def neighbors(a, b) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


class UF:
    def __init__(self):
        self.p = {}

    def root(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def join(self, a, b):
        self.p[self.root(a)] = self.root(b)


def netlist(changes: dict[str, str]) -> dict:
    """Parts and Pi pins from circuit-reference.json, with value changes applied."""
    parts = {}
    for comp in CANON["components"]:
        part = parts.setdefault(comp["ref"], {"value": comp["value"], "pins": {}, "internal": []})
        part["pins"].update(comp["pins"])
        part["internal"] += comp.get("internal_connections", [])
    for ref, value in changes.items():
        parts[ref]["value"] = value
    del parts["J1"]
    pi = {row[1]: {"gpio": row[2], "net": row[3]} for row in CANON["pins"]}
    return {"parts": parts, "pi": pi}


class Layout:
    """Parts, wires and copper links on the board; validate() proves the netlist."""

    def __init__(self, nets: dict):
        self.nets = nets
        self.parts = []      # {ref, pins: {pin: hole}, stage, how}
        self.wires = []      # insulated, component side: {a, b, net, stage}
        self.links = []      # bare, copper side: {a, b, net, stage}
        self.pi = []         # cut Dupont leads: {physical, hole, net, stage}
        self.keepout = {}    # hole -> reason (under a body or a lying lead)
        self.used = {}       # hole -> owner

    def _use(self, h, owner):
        assert h not in self.used, f"{name(h)} already holds {self.used[h]}, not {owner}"
        assert h not in self.keepout, f"{name(h)} is covered by {self.keepout[h]} ({owner})"
        self.used[h] = owner

    def part(self, ref, pins, stage, how="", covers=()):
        spec = self.nets["parts"][ref]
        assert set(pins) == set(spec["pins"]), ref
        placed = {pin: hole(h) for pin, h in pins.items()}
        for pin, h in placed.items():
            self._use(h, f"{ref}.{pin}")
        for h in covers:
            self.keepout[hole(h)] = ref
        self.parts.append({"ref": ref, "value": spec["value"], "pins": placed,
                           "stage": stage, "how": how})

    def wire(self, a, b, net, stage, via=()):
        """Insulated wire; `via` are (row, col) bends for routing around parts."""
        a, b = hole(a), hole(b)
        self._use(a, f"cable {net}")
        self._use(b, f"cable {net}")
        self.wires.append({"a": a, "b": b, "net": net, "stage": stage, "via": list(via)})

    def link(self, a, b, net, stage):
        """Bare link on the copper side between neighboring pads/rail; uses no hole."""
        a, b = hole(a), hole(b)
        assert neighbors(a, b), f"copper link {name(a)}–{name(b)} is not between neighbors"
        assert conductor(a) != conductor(b), f"link {name(a)}–{name(b)} joins one piece to itself"
        self.links.append({"a": a, "b": b, "net": net, "stage": stage})

    def lead(self, physical, h, stage, via=()):
        """Cut Dupont lead from Pi header pin `physical`; drawn entering from the left."""
        net = self.nets["pi"][physical]["net"] if physical in self.nets["pi"] else "GND"
        self._use(hole(h), f"Pi {physical}")
        self.pi.append({"physical": physical, "hole": hole(h), "net": net, "stage": stage,
                        "via": list(via)})

    def connectivity(self, extra=()):
        uf = UF()
        for h in self.used:
            uf.join(h, conductor(h))
        for w in self.wires:
            uf.join(w["a"], w["b"])
        for l in self.links:
            uf.join(conductor(l["a"]), conductor(l["b"]))
        for p in self.parts:
            for a, b in self.nets["parts"][p["ref"]]["internal"]:
                uf.join(p["pins"][a], p["pins"][b])
        for a, b in extra:
            uf.join(a, b)
        return uf

    def terminals(self):
        """(hole, net, label) for every part pin and Pi lead."""
        for p in self.parts:
            spec = self.nets["parts"][p["ref"]]["pins"]
            for pin, h in p["pins"].items():
                yield h, spec[pin], f"{p['ref']}.{pin}"
        for lead in self.pi:
            yield lead["hole"], lead["net"], f"Pi {lead['physical']}"

    def validate(self):
        placed = {p["ref"] for p in self.parts}
        assert placed == set(self.nets["parts"]), f"missing parts: {set(self.nets['parts']) - placed}"
        uf = self.connectivity()
        by_root = defaultdict(set)
        for h, net, label in self.terminals():
            by_root[uf.root(h)].add(net)
        for root, nets in by_root.items():
            nets.discard("NC_U1_7")
            assert len(nets) <= 1, f"nets shorted together: {sorted(nets)}"
        roots = defaultdict(set)
        for h, net, label in self.terminals():
            if net != "NC_U1_7":
                roots[net].add(uf.root(h))
        split = {net: len(r) for net, r in roots.items() if len(r) > 1}
        assert not split, f"nets split into pieces: {split}"
        for w in self.wires + self.links:
            assert roots[w["net"]] == {uf.root(conductor(w["a"]))}, f"{w} labelled with the wrong net"
        pi_nets = {lead["net"] for lead in self.pi}
        assert {"3V3", "5V", "GND", "TX", "OPT_RX", "LED_TX", "LED_RX", "PANIC"} <= pi_nets
        return roots

    def ascii(self) -> str:
        """Component-side map for design review: one cell per hole."""
        grid = [["  ·  " if c not in RAILS else "  |  " for c in range(1, COLS + 1)]
                for _ in range(ROWS)]
        for h, owner in self.used.items():
            grid[h[0] - 1][h[1] - 1] = f"{owner.split()[-1][:5]:^5}"
        for h, ref in self.keepout.items():
            if h not in self.used:
                grid[h[0] - 1][h[1] - 1] = f"({ref[:3]})".center(5)
        head = "     " + "".join(f"{c:^5}" for c in range(1, COLS + 1))
        return "\n".join([head] + [f"{r + 1:>3}  " + "".join(row) for r, row in enumerate(grid)])
