"""Generate the FaroNet revision-7 breadboard plan from an explicit hole model.

One basic Faro per breadboard; RGB is no longer part of the design. The
electrical netlist comes from circuit-reference.json; this file only decides
where each terminal goes. Design rules, checked by Layout.validate():

- Every part and jumper end sits on the A–E half, except three landmarks:
  the button legs, the strips directly below the LM393, and the IR emitter
  on the last two columns. The team's board prints F–J column numbers in
  reverse, so the guide names those holes by landmark, not by number.
- D1 (row h) and Q2 (row c) are mirror rows, so a second identical Faro
  rotated 180° aligns emitter to detector exactly.
- One terminal per hole, no hole under a part body, no clip joining nets.

The model checks copper connectivity only, not analogue behaviour or optics.
"""
from pathlib import Path
import collections
import html
import json
import math
import re

HERE = Path(__file__).resolve().parent
CANON = json.loads((HERE / "circuit-reference.json").read_text())
REVISION = 7

PARTS = {}
for _c in CANON["components"]:
    PARTS.setdefault(_c["ref"], dict(_c, pins={}))["pins"].update(_c["pins"])
PI_PINS = {row[1]: row for row in CANON["pins"]}  # physical -> row

NET_COLOR = {
    "5V": "#c0392b", "3V3": "#7d3cb5", "GND": "#3d4b58", "TX": "#1565c0",
    "OPT_RX": "#00838f", "LED_TX": "#2e7d32", "LED_RX": "#b07d00",
    "PANIC": "#ad1457", "VBIAS": "#8d6e00", "VTH": "#6d4c41",
    "SENSE": "#e65100", "Q_BASE": "#3949ab", "IR_A": "#c0392b",
    "IR_K": "#5d4037", "GREEN_A": "#2e7d32", "YELLOW_A": "#b07d00",
}
STAGES = {
    "power": "1 · Alimentación", "leds": "2 · LED verde y amarillo",
    "panic": "3 · Botón de pánico", "tx": "4 · Emisor IR",
    "rx": "5 · Receptor",
}

# --- Geometry -------------------------------------------------------------
PITCH = 22
X0 = 420                       # x of column 1
ROW_Y = {r: 190 + i * PITCH for i, r in enumerate("abcde")}
ROW_Y.update({r: ROW_Y["e"] + 3 * PITCH + i * PITCH for i, r in enumerate("fghij")})
RAIL_Y = {"T3": 100, "TG": 122, "B5": ROW_Y["j"] + 68, "BG": ROW_Y["j"] + 90}
RAIL_NET = {"T3": "3V3", "TG": "GND", "B5": "5V", "BG": "GND"}
COLUMNS = 63
WIDTH, HEIGHT = 2060, 760
TOP_HALF, BOTTOM_HALF = "abcde", "fghij"


def rail_offset(i):
    """Rails have 50 holes in groups of five, split after hole 25."""
    return i - 1 + (i - 1) // 5 + (1 if i > 25 else 0)


def xy(hole):
    if hole.startswith("PI:"):
        n = int(hole[3:])
        return (218 if n % 2 else 252), 190 + (n - 1) // 2 * 26
    if ":" in hole:
        rail, i = hole.split(":")
        return X0 + (1.5 + rail_offset(int(i))) * PITCH, RAIL_Y[rail]
    return X0 + (int(hole[1:]) - 1) * PITCH, ROW_Y[hole[0]]


def rail_near(rail, column, taken):
    """Free rail hole closest to a column, so rail legs stay short."""
    best = min((i for i in range(1, 51) if f"{rail}:{i}" not in taken),
               key=lambda i: abs(2.5 + rail_offset(i) - column))
    return f"{rail}:{best}"


def valid_hole(a):
    return (re.fullmatch(r"[a-j](?:[1-9]|[1-5][0-9]|6[0-3])", a)
            or re.fullmatch(r"(?:T3|TG|B5|BG):(?:[1-9]|[1-4][0-9]|50)", a)
            or re.fullmatch(r"PI:(?:[1-9]|[1-3][0-9]|40)", a)) is not None


def on_fj(hole):
    return ":" not in hole and hole[0] in BOTTOM_HALF


class UF:
    def __init__(self):
        self.p = {}

    def root(self, a):
        self.p.setdefault(a, a)
        if self.p[a] != a:
            self.p[a] = self.root(self.p[a])
        return self.p[a]

    def join(self, a, b):
        self.p[self.root(a)] = self.root(b)


# The only places allowed on the F–J half, and how to find them on the board.
FJ_LANDMARKS = {
    "S1": "Patas inferiores del botón: entran solas al montar S1 sobre el canal.",
    "U1": "Las cuatro tiras justo debajo del LM393 (patas 5–8).",
    "D1": "Las dos últimas tiras del borde derecho, frente a Q2.",
}


class Layout:
    def __init__(self):
        self.parts, self.wires = [], []
        self.claims, self.nets = {}, {}
        self.keepout = {}

    def claim(self, hole, owner, net):
        assert valid_hole(hole), "Dirección inválida: " + hole
        assert hole not in self.claims, (hole, owner, self.claims.get(hole))
        self.claims[hole], self.nets[hole] = owner, net

    def part(self, ref, pins, stage, keepout=(), landmark=None):
        spec = PARTS[ref]
        assert set(pins) == set(spec["pins"]), (ref, set(pins) ^ set(spec["pins"]))
        for pin, hole in pins.items():
            self.claim(hole, f"{ref}.{pin}", spec["pins"][pin])
        for hole in keepout:
            self.keepout[hole] = ref
        self.parts.append(dict(ref=ref, value=spec["value"], pins=pins,
                               stage=stage, landmark=landmark))

    def resistor(self, ref, a, b, stage):
        """Horizontal resistors keep the holes under their body free."""
        lo, hi = sorted((int(a[1:]), int(b[1:])))
        self.part(ref, {"1": a, "2": b}, stage, [f"{a[0]}{c}" for c in range(lo + 1, hi)])

    def wire(self, a, b, net, stage, why, landmark=None):
        wid = f"W{len(self.wires) + 1:02d}"
        for hole in (a, b):
            self.claim(hole, wid, net)
        self.wires.append(dict(id=wid, a=a, b=b, net=net, stage=stage,
                               why=why, landmark=landmark))

    def pi(self, physical, hole, stage):
        row = PI_PINS[physical]
        self.wire(f"PI:{physical}", hole, row[3], stage,
                  f"Pi físico {physical} · {row[2]} · {row[4]}")

    def to_rail(self, rail, column):
        return rail_near(rail, column, self.claims)

    def pins(self, ref):
        return next(p for p in self.parts if p["ref"] == ref)["pins"]

    def owner(self, hole):
        ref = self.claims[hole].split(".")[0]
        return next((p for p in self.parts if p["ref"] == ref), None) or \
            next(w for w in self.wires if w["id"] == ref)

    def copper(self):
        uf = UF()
        for c in range(1, COLUMNS + 1):
            for half in (TOP_HALF, BOTTOM_HALF):
                for r in half:
                    uf.join(f"{half[0]}{c}", f"{r}{c}")
        for rail in RAIL_Y:
            for lo, hi in ((1, 25), (26, 50)):
                for i in range(lo, hi + 1):
                    uf.join(f"{rail}:{lo}", f"{rail}:{i}")
        for w in self.wires:
            uf.join(w["a"], w["b"])
        # S1 joins each pair of legs permanently; never the press itself.
        for p in self.parts:
            for a, b in PARTS[p["ref"]].get("internal_connections", []):
                uf.join(p["pins"][a], p["pins"][b])
        return uf

    def validate(self):
        uf = self.copper()
        nets = dict(self.nets)
        for rail, net in RAIL_NET.items():
            for i in (1, 26):
                nets.setdefault(f"{rail}:{i}", net)
        roots = collections.defaultdict(set)
        net_roots = collections.defaultdict(set)
        for hole, net in nets.items():
            roots[uf.root(hole)].add(net)
            net_roots[net].add(uf.root(hole))
        shorts = [sorted(n) for n in roots.values() if len(n) > 1]
        assert not shorts, "Clip une redes distintas: " + str(shorts)
        split = sorted(n for n, r in net_roots.items() if len(r) > 1)
        assert not split, "Red sin continuidad: " + str(split)
        expected = {f"{c['ref']}.{p}" for c in CANON["components"]
                    if c["ref"] != "J1" for p in c["pins"]}
        placed = {f"{p['ref']}.{pin}" for p in self.parts for pin in p["pins"]}
        assert placed == expected, placed ^ expected
        wired = {int(w["a"][3:]) for w in self.wires if w["a"].startswith("PI:")}
        assert wired == set(PI_PINS), wired ^ set(PI_PINS)
        for p in self.parts:
            if p["ref"][0] == "R" and p["ref"] != "RV1":
                a, b = p["pins"].values()
                assert uf.root(a) != uf.root(b), "Resistencia puenteada " + p["ref"]
        assert len({uf.root(f"PI:{n}") for n in (1, 2, 6)}) == 3, "Alimentaciones unidas"
        for n in (11, 13, 15, 16, 18):
            assert uf.root(f"PI:{n}") != uf.root("PI:2"), f"GPIO físico {n} unido a 5 V"
        blocked = sorted(set(self.claims) & set(self.keepout))
        assert not blocked, "Agujero bajo el cuerpo de una pieza: " + str(blocked)
        for hole in self.claims:
            if on_fj(hole):
                assert self.owner(hole)["landmark"] in FJ_LANDMARKS, \
                    f"{hole} ({self.claims[hole]}) en F–J fuera de un punto de referencia"
        s1 = self.pins("S1")
        assert uf.root(s1["1"]) == uf.root(s1["2"]) and uf.root(s1["3"]) == uf.root(s1["4"])
        assert uf.root(s1["1"]) != uf.root(s1["3"]), "Botón puenteado en reposo"
        assert len({uf.root(h) for h in self.pins("RV1").values()}) == 3, "Trimpot puenteado"
        nc = self.pins("U1")["7 OUT2"]
        assert sum(uf.root(h) == uf.root(nc) for h in self.claims) == 1, "U1.7 no aislado"
        d1, q2 = self.pins("D1"), self.pins("Q2")
        mirror = dict(zip("abcdefghij", "jihgfedcba"))
        assert {h[0] for h in d1.values()} == {mirror[h[0]] for h in q2.values()}, "D1/Q2 no espejados"
        assert {h[1:] for h in d1.values()} == {h[1:] for h in q2.values()} == {"62", "63"}
        self.hole_nets = {h: next(iter(roots[uf.root(h)])) for h in uf.p if roots.get(uf.root(h))}
        self.uf = uf
        return self


def make(trimpot="RM063"):
    """Build and validate the plan. RM065 moves only the wiper, to e51."""
    l = Layout()
    # 1 · Power. Each rail is modelled split at 25/26 and bridged.
    l.pi(1, "T3:2", "power")
    l.pi(2, "B5:2", "power")
    l.pi(6, "TG:2", "power")
    l.wire("TG:4", "BG:4", "GND", "power", "Une solo los rieles GND de arriba y abajo")
    for rail, net in RAIL_NET.items():
        l.wire(f"{rail}:25", f"{rail}:26", net, "power",
               "Puente entre mitades del riel; inofensivo si tu riel es continuo")
    l.part("C1", {"+": l.to_rail("B5", 40), "−": l.to_rail("BG", 40)}, "power")
    # 2 · Indicators: GPIO -> 1 kΩ -> anode; cathode (short leg) to the GND rail.
    for physical, ref_r, ref_d, col in ((15, "R10", "D2", 3), (16, "R11", "D3", 10)):
        l.pi(physical, f"a{col}", "leds")
        l.resistor(ref_r, f"b{col}", f"b{col + 4}", "leds")
        l.part(ref_d, {"A": f"c{col + 4}", "K": l.to_rail("TG", col + 4.5)}, "leds")
    # 3 · Panic. DTS-6 rotated 90°: pairs 1–2 (GND) and 3–4 (PANIC).
    l.part("S1", {"1": "e20", "2": "f20", "3": "e18", "4": "f18"}, "panic", landmark="S1")
    l.part("R12", {"1": l.to_rail("T3", 18), "2": "a18"}, "panic")
    l.pi(18, "b18", "panic")
    l.wire("a20", l.to_rail("TG", 20), "GND", "panic", "Pareja GND del botón al riel")
    # 4 · TX driver. Q1 is C-B-E seen from its flat face, which faces the
    # central channel: collector d59, base d60, emitter d61.
    l.pi(11, "a56", "tx")
    l.resistor("R2", "b56", "b60", "tx")
    l.part("R3", {"1": "a60", "2": l.to_rail("TG", 60)}, "tx")
    l.part("Q1", {"C": "d59", "B": "d60", "E": "d61"}, "tx")
    l.wire("a61", l.to_rail("TG", 61), "GND", "tx", "Emisor de Q1 a GND")
    l.part("D1", {"A": "h62", "K": "h63"}, "tx", landmark="D1")
    l.part("R1", {"1": l.to_rail("B5", 62), "2": "j62"}, "tx", landmark="D1")
    l.wire("c59", "g63", "IR_K", "tx", "Colector de Q1 al cátodo de D1 (cruza el canal)",
           landmark="D1")
    # 5 · Receiver. LM393 notch to the right: pins 4..1 on row e at columns
    # 50..53, pins 5..8 directly below on row f.
    l.part("U1", {"4 GND": "e50", "3 IN1+": "e51", "2 IN1−": "e52", "1 OUT1": "e53",
                  "5 IN2+": "f50", "6 IN2−": "f51", "7 OUT2": "f52", "8 VCC": "f53"},
           "rx", landmark="U1")
    l.wire("d50", l.to_rail("TG", 50), "GND", "rx", "U1.4 a GND")
    l.wire("j50", l.to_rail("BG", 50), "GND", "rx", "U1.5 (entrada sin usar) a GND",
           landmark="U1")
    l.wire("j53", l.to_rail("B5", 53), "5V", "rx", "U1.8 alimentación 5 V", landmark="U1")
    l.part("C2", {"1": "i53", "2": "i50"}, "rx", ["i51", "i52"], landmark="U1")
    l.part("C3", {"1": "h51", "2": "h50"}, "rx", landmark="U1")
    l.part("R9", {"1": "j51", "2": l.to_rail("BG", 51)}, "rx", landmark="U1")
    # Output side: pull-up, hysteresis toward VTH and the Pi input.
    l.resistor("R6", "a53", "a49", "rx")
    l.part("R5", {"1": l.to_rail("T3", 53), "2": "b53"}, "rx")
    l.pi(13, "c53", "rx")
    l.wire("b49", "b51", "VTH", "rx", "Histéresis R6 a U1.3")
    # VBIAS hub next to the chip, so R4 lands directly on U1.2 (SENSE).
    l.resistor("R4", "c48", "c52", "rx")
    l.wire("d48", "g51", "VBIAS", "rx", "VBIAS a U1.6 (cruza el canal)", landmark="U1")
    # RV1 stands apart with free space around it. Upright RM063: ends d40/d42,
    # wiper c41, adjustment slot facing the channel (row e side, kept clear).
    # A horizontal RM065 puts its wiper in b41, which stays reserved.
    wiper, free = ("c41", "b41") if trimpot == "RM063" else ("b41", "c41")
    l.part("RV1", {"1 extremo": "d40", "2 cursor": wiper, "3 extremo": "d42"}, "rx",
           ["d41", "c40", "c42", "e40", "e41", "e42", free])
    l.part("R8", {"1": l.to_rail("T3", 40), "2": "a40"}, "rx")
    l.wire("b40", "b48", "VBIAS", "rx", "VBIAS de RV1/R8 a R4 y U1.6")
    l.wire("a41", "d51", "VTH", "rx", "Cursor de RV1 a U1.3")
    l.wire("a42", l.to_rail("TG", 42), "GND", "rx", "Extremo 3 de RV1 a GND")
    l.part("Q2", {"E": "c62", "C": "c63"}, "rx")
    l.wire("a62", l.to_rail("TG", 62), "GND", "rx", "Emisor de Q2 a GND")
    l.wire("a63", "d52", "SENSE", "rx", "Colector de Q2 al nodo SENSE (U1.2)")
    return l.validate()


# --- Drawing --------------------------------------------------------------
def esc(s):
    return html.escape(str(s), quote=True)


def color(net):
    return NET_COLOR.get(net, "#455a64")


class Drawing:
    def __init__(self, layout):
        self.l, self.out, self.badges = layout, [], []

    def add(self, s):
        self.out.append(s)

    def text(self, x, y, s, cls="t", anchor="start"):
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}">{esc(s)}</text>')

    def badge(self, x, y, s, stage):
        w = len(s) * 7 + 12
        self.badges.append(f'<g data-stage="{stage}" class="badge"><rect x="{x - w / 2:.1f}" y="{y - 10:.1f}" '
                 f'width="{w:.1f}" height="19" rx="5"/><text x="{x:.1f}" y="{y + 4:.1f}" '
                 f'text-anchor="middle">{esc(s)}</text></g>')

    def board(self):
        left, right = X0 - 34, X0 + (COLUMNS - 1) * PITCH + 34
        self.add(f'<rect x="{left}" y="{RAIL_Y["T3"] - 26}" width="{right - left}" '
                 f'height="{RAIL_Y["BG"] - RAIL_Y["T3"] + 52}" rx="14" class="board"/>')
        mid = (ROW_Y["e"] + ROW_Y["f"]) / 2
        self.add(f'<rect x="{left + 10}" y="{mid - 9}" width="{right - left - 20}" height="18" class="trench"/>')
        for rail, net in RAIL_NET.items():
            y = RAIL_Y[rail] + (-11 if rail in ("T3", "B5") else 11)
            self.add(f'<path d="M{left + 22} {y} H{right - 22}" stroke="{color(net)}" stroke-width="2.5" opacity=".7"/>')
            label = {"T3": "+3,3 V", "TG": "GND", "B5": "+5 V", "BG": "GND"}[rail]
            self.text(right + 8, RAIL_Y[rail] + 5, label, "rail")
        for c in range(1, COLUMNS + 1):
            if c == 1 or c % 5 == 0:
                self.text(X0 + (c - 1) * PITCH, ROW_Y["a"] - 22, c, "num", "middle")
        for r in "abcdefghij":
            self.text(left + 14, ROW_Y[r] + 4, r, "row", "middle")
            self.text(right - 14, ROW_Y[r] + 4, r, "row", "middle")
        self.text((left + right) / 2, RAIL_Y["BG"] + 92,
                  "Mitad F–J: tu tablero imprime estos números al revés. Ubica cada agujero de F–J "
                  "por su columna física de arriba o por su punto de referencia.", "warn", "middle")
        holes = [f"{r}{c}" for r in "abcdefghij" for c in range(1, COLUMNS + 1)]
        holes += [f"{rail}:{i}" for rail in RAIL_Y for i in range(1, 51)]
        for h in holes:
            x, y = xy(h)
            used = h in self.l.claims
            net = self.l.hole_nets.get(h, "")
            title = f"{h} · {self.l.claims[h]} · {net}" if used else \
                f"{h} · " + (f"clip {net}" if net else "libre")
            fill = color(net) if used else "#f7f9fa"
            self.add(f'<circle cx="{x:.1f}" cy="{y}" r="{4.6 if used else 3.6}" class="hole" '
                     f'data-hole="{h}" data-net="{net}" fill="{fill}"><title>{esc(title)}</title></circle>')

    def header(self):
        self.add('<rect x="196" y="172" width="78" height="514" rx="8" class="pi"/>')
        self.text(235, 160, "Raspberry Pi", "t", "middle")
        self.text(235, 704, "Header J8 · pin 1 arriba", "small", "middle")
        labels = collections.defaultdict(list)
        for n in range(1, 41):
            x, y = xy(f"PI:{n}")
            used = n in PI_PINS
            net = PI_PINS[n][3] if used else ""
            tip = f"Físico {n}" + (f" · {PI_PINS[n][2]} · {net}" if used else "")
            self.add(f'<rect x="{x - 6}" y="{y - 6}" width="12" height="12" rx="2" class="pin" '
                     f'fill="{color(net) if used else "#cfd8dc"}" data-net="{net}"><title>{esc(tip)}</title></rect>')
            if used:
                labels[y].append(f"{n} {net}")
        # Labels sit left of the header so jumpers never cover them.
        for y, items in labels.items():
            self.text(184, y + 4, " · ".join(items), "pinlabel", "end")

    def route(self, w, index):
        (x, y), (X, Y) = xy(w["a"]), xy(w["b"])
        if w["a"].startswith("PI:"):
            lane = 290 + sorted(PI_PINS).index(int(w["a"][3:])) * 8
            below = w["b"].startswith(("B5", "BG"))
            level = RAIL_Y["BG"] + 22 if below else 48 + sorted(PI_PINS).index(int(w["a"][3:])) * 4
            return f"M{x} {y} H{lane} V{level} H{X:.1f} V{Y}"
        if w["a"] == "TG:4":
            edge = X0 - 52
            return f"M{x:.1f} {y} V{y - 16} H{edge} V{Y + 16} H{X:.1f} V{Y}"
        lift = min(40, 9 + math.hypot(X - x, Y - y) * 0.1)
        if y >= ROW_Y["f"] and Y >= ROW_Y["f"]:
            cy = max(y, Y) + lift
        else:
            cy = min(y, Y) - lift
        return f"M{x:.1f} {y} Q{(x + X) / 2:.1f} {cy:.1f} {X:.1f} {Y}"

    def wires(self):
        for i, w in enumerate(self.l.wires):
            d = self.route(w, i)
            self.add(f'<g class="jumper" data-stage="{w["stage"]}" data-net="{w["net"]}" data-id="{w["id"]}">'
                     f'<title>{w["id"]}: {w["a"]} ↔ {w["b"]} · {esc(w["why"])}</title>'
                     f'<path d="{d}" class="wire-shadow"/><path d="{d}" class="wire" stroke="{color(w["net"])}"/></g>')

    def resistor(self, p):
        (x, y), (X, Y) = (xy(h) for h in p["pins"].values())
        cx, cy = (x + X) / 2, (y + Y) / 2
        angle = math.degrees(math.atan2(Y - y, X - x))
        length = min(46, math.hypot(X - x, Y - y) - 14)
        self.add(f'<g class="part" data-stage="{p["stage"]}" data-ref="{p["ref"]}"><title>{p["ref"]} · '
                 f'{esc(p["value"])}</title><path d="M{x:.1f} {y} L{X:.1f} {Y}" class="lead"/>'
                 f'<g transform="translate({cx:.1f} {cy:.1f}) rotate({angle:.1f})"><rect x="{-length / 2:.1f}" '
                 f'y="-6" width="{length:.1f}" height="12" rx="5" class="resistor"/></g></g>')
        bx, by = (cx, cy - 15) if abs(Y - y) < 1 else (cx + 44, cy + 6)
        self.badge(bx, by, f'{p["ref"]} {p["value"]}', p["stage"])

    def part(self, p):
        ref, pins, stage = p["ref"], p["pins"], p["stage"]
        pts = {k: xy(h) for k, h in pins.items()}
        g = (f'<g class="part" data-stage="{stage}" data-ref="{ref}"><title>{ref} · {esc(p["value"])} · '
             + esc(", ".join(f"{k}={h}" for k, h in pins.items())) + "</title>")
        if ref in ("D2", "D3"):
            (ax, ay), (kx, ky) = pts["A"], pts["K"]
            fill = "#66bb6a" if ref == "D2" else "#ffd54f"
            top = ky + 24
            self.add(g + f'<path d="M{ax} {ay} L{ax} {top} M{kx:.1f} {ky} L{kx:.1f} {top}" class="lead"/>'
                     f'<circle cx="{(ax + kx) / 2:.1f}" cy="{top}" r="10" fill="{fill}" stroke="#555"/></g>')
            self.badge((ax + kx) / 2 - 40, top, "D2 verde" if ref == "D2" else "D3 amarillo", stage)
        elif ref == "Q1":
            xs = sorted(x for x, _ in pts.values())
            ey, bx = pts["B"][1], pts["B"][0]
            self.add(g + f'<path d="M{xs[0] - 7} {ey + 7} A28 28 0 0 1 {xs[-1] + 7} {ey + 7} Z" class="to92"/>'
                     f'<path d="M{xs[0] - 7} {ey + 7} H{xs[-1] + 7}" stroke="#ffb300" stroke-width="3"/>')
            for k, (px, py) in pts.items():
                self.text(px, py + 19, k, "pinlabel", "middle")
            self.add("</g>")
            self.badge(bx, ey - 34, "Q1 cara plana ↓", stage)
        elif ref == "U1":
            xs = [x for x, _ in pts.values()]
            left, right = min(xs) - 10, max(xs) + 10
            top, bottom = ROW_Y["e"] + 8, ROW_Y["f"] - 8
            mid = (top + bottom) / 2
            self.add(g + f'<rect x="{left}" y="{top}" width="{right - left}" height="{bottom - top}" rx="4" class="chip"/>'
                     f'<path d="M{right} {mid - 8} a8 8 0 0 0 0 16" fill="#b0bec5"/>')
            for k, (px, py) in pts.items():
                self.text(px, py + (16 if py < mid else -9), k.split()[0], "chiptext", "middle")
            self.add("</g>")
        elif ref == "S1":
            xs = [x for x, _ in pts.values()]
            mx = sum(xs) / 4
            self.add(g + f'<rect x="{min(xs) - 9}" y="{ROW_Y["e"] - 9}" width="{max(xs) - min(xs) + 18}" '
                     f'height="{ROW_Y["f"] - ROW_Y["e"] + 18}" rx="4" class="button"/>'
                     f'<circle cx="{mx}" cy="{(ROW_Y["e"] + ROW_Y["f"]) / 2}" r="11" fill="#263238"/></g>')
            self.badge(mx, ROW_Y["e"] - 22, "S1 pánico", stage)
        elif ref == "RV1":
            xs = [x for x, _ in pts.values()]
            ys = [y for _, y in pts.values()]
            mx = sum(xs) / 3
            self.add(g + f'<rect x="{min(xs) - 8}" y="{min(ys) - 9}" width="{max(xs) - min(xs) + 16}" '
                     f'height="{max(ys) - min(ys) + 18}" rx="4" class="trim"/>'
                     f'<circle cx="{mx:.1f}" cy="{max(ys) + 1}" r="7" fill="#eceff1" stroke="#455a64"/>'
                     f'<path d="M{mx - 5:.1f} {max(ys) + 1} h10" stroke="#455a64" stroke-width="2"/></g>')
            self.badge(mx - 92, max(ys) + 2, "RV1 ranura de ajuste ↓", stage)
        elif ref in ("C2", "C3"):
            (x, y), (X, Y) = pts.values()
            cx, cy = (x + X) / 2, (y + Y) / 2 + 2
            self.add(g + f'<path d="M{x} {y} L{cx} {cy} L{X} {Y}" class="lead"/>'
                     f'<ellipse cx="{cx}" cy="{cy}" rx="10" ry="7" class="ceramic"/></g>')
            self.badge(cx + (-26 if ref == "C3" else 26), cy, ref, stage)
        elif ref == "C1":
            (x, y), (X, Y) = pts["+"], pts["−"]
            self.add(g + f'<path d="M{x:.1f} {y} V{Y + 18} M{X:.1f} {Y} V{Y + 18}" class="lead"/>'
                     f'<rect x="{x - 15:.1f}" y="{Y + 16}" width="30" height="36" rx="7" class="electro"/>'
                     f'<rect x="{x + 4:.1f}" y="{Y + 19}" width="7" height="30" rx="2" fill="#cfd8dc"/></g>')
            self.badge(x + 72, Y + 34, "C1 franja = −", stage)
        elif ref in ("D1", "Q2"):
            cy = sum(y for _, y in pts.values()) / 2
            base = X0 + (COLUMNS - 1) * PITCH + 48
            body = "#b3c7e6" if ref == "D1" else "#263238"
            self.add(g)
            for (k, (px, py)), dy in zip(pts.items(), (-6, 6)):
                self.add(f'<path d="M{px} {py} V{cy + dy} H{base}" class="lead"/>')
            self.add(f'<path d="M{base} {cy - 12} h28 a12 12 0 0 1 0 24 h-28 Z" fill="{body}" stroke="#455a64"/>')
            arrow = "#c0392b" if ref == "D1" else "#00838f"
            x1, x2 = (base + 48, base + 110) if ref == "D1" else (base + 110, base + 48)
            tip = -9 if ref == "D1" else 9
            self.add(f'<path d="M{x1} {cy} H{x2}" stroke="{arrow}" stroke-width="3" stroke-dasharray="7 5"/>'
                     f'<polygon points="{x2},{cy} {x2 + tip},{cy - 6} {x2 + tip},{cy + 6}" fill="{arrow}"/></g>')
            label = "D1 IR · A h62 K h63" if ref == "D1" else "Q2 PT333 · E c62 C c63"
            self.badge(base + 60, cy - 24, label, stage)
        else:
            raise ValueError(ref)

    def draw(self):
        self.add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" '
                 f'height="{HEIGHT}" role="img" aria-label="Plano de protoboard FaroNet revisión {REVISION}">'
                 f'<style>{SVG_CSS}</style><rect width="100%" height="100%" fill="#ffffff"/>')
        self.text(30, 30, f"FaroNet · un Faro por protoboard · revisión {REVISION} · sin RGB", "title")
        self.board()
        self.header()
        for p in self.l.parts:
            if p["ref"][0] == "R" and p["ref"] != "RV1":
                self.resistor(p)
            else:
                self.part(p)
        self.wires()
        self.out += self.badges  # labels on top, never hidden by jumpers
        self.add("</svg>")
        return "".join(self.out)


SVG_CSS = (
    ".t{font:600 15px system-ui,sans-serif;fill:#1c2b36}.title{font:700 20px system-ui,sans-serif;fill:#1c2b36}"
    ".small{font:12px system-ui,sans-serif;fill:#37474f}.num{font:11px system-ui,sans-serif;fill:#546e7a}"
    ".row{font:700 11px system-ui,sans-serif;fill:#78909c}.rail{font:700 12px system-ui,sans-serif;fill:#37474f}"
    ".warn{font:600 13px system-ui,sans-serif;fill:#a04000}.pinlabel{font:600 11px system-ui,sans-serif;fill:#263238}"
    ".chiptext{font:700 10px system-ui,sans-serif;fill:#eceff1}.board{fill:#f1ece3;stroke:#cbbfa9}"
    ".trench{fill:#e2d9c8}.pi{fill:#2e7d32;fill-opacity:.15;stroke:#2e7d32}.hole{stroke:#9e9e9e;stroke-width:.8}"
    ".lead{stroke:#8d9aa3;stroke-width:2.4;fill:none}.resistor{fill:#e7cf9f;stroke:#9c7a3c}"
    ".to92{fill:#263238}.chip{fill:#263238}.button{fill:#546e7a}.trim{fill:#1e5aa8}"
    ".ceramic{fill:#e0b36b;stroke:#8d6e3a}.electro{fill:#1f3f66}"
    ".wire{fill:none;stroke-width:3.4;stroke-linecap:round}"
    ".wire-shadow{fill:none;stroke:#fff;stroke-width:6.5;stroke-linecap:round}"
    ".badge rect{fill:#fff;fill-opacity:.94;stroke:#9fb4c2}"
    ".badge text{font:700 11px system-ui,sans-serif;fill:#1c2b36}"
)


def facing_svg():
    """Two identical Faros, the second rotated 180°: rows c and h swap heights."""
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 370" width="980" height="370" role="img" '
           'aria-label="Dos Faros enfrentados"><style>text{font:600 14px system-ui,sans-serif;fill:#1c2b36}'
           '.s{font:12px system-ui,sans-serif}</style><rect width="100%" height="100%" fill="#fff"/>']
    rows = "abcdefghij"
    for title, x, flip in (("Faro 1", 60, False), ("Faro 2 (girado 180°)", 600, True)):
        out.append(f'<rect x="{x}" y="60" width="320" height="250" rx="12" fill="#f1ece3" stroke="#cbbfa9"/>')
        out.append(f'<text x="{x + 160}" y="44" text-anchor="middle">{title}</text>')
        for i in range(10):
            label = rows[9 - i] if flip else rows[i]
            y = 90 + i * 22 + (12 if i >= 5 else 0)
            out.append(f'<text x="{x + (300 if flip else 14)}" y="{y + 4}" class="s">{label}</text>')
            if label in "ch":
                part = "Q2" if label == "c" else "D1"
                fill = "#263238" if part == "Q2" else "#b3c7e6"
                bx = x + 320 if not flip else x - 44
                tx = bx - 46 if not flip else bx + 90
                out.append(f'<rect x="{bx}" y="{y - 9}" width="44" height="18" rx="9" fill="{fill}" stroke="#455a64"/>')
                out.append(f'<text x="{tx}" y="{y + 5}" text-anchor="middle" class="s">{part} fila {label}</text>')
    for y, stroke in ((90 + 2 * 22, "#c0392b"), (90 + 7 * 22 + 12, "#c0392b")):
        out.append(f'<path d="M430 {y} H550" stroke="{stroke}" stroke-width="3" stroke-dasharray="7 5"/>')
    out.append('<text x="490" y="345" text-anchor="middle" class="s">D1 de cada Faro queda a la altura de Q2 del '
               'otro. Prueba una dirección a la vez; los bordes del tablero no garantizan la alineación.</text></svg>')
    return "".join(out)


# --- Guide page -----------------------------------------------------------
def table(head, rows):
    return ('<div class="wrap"><table><thead><tr>' + "".join(f"<th>{h}</th>" for h in head)
            + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
            + "</tbody></table></div>")


def spot(layout, hole):
    note = ""
    if on_fj(hole):
        note = f' <span class="fj">F–J · {esc(FJ_LANDMARKS[layout.owner(hole)["landmark"]])}</span>'
    return f"<code>{hole}</code>{note}"


STAGE_CHECKS = {
    "power": ["Sin la Pi: entre 3V3, 5V y GND no suena continuidad en ningún par.",
              "Sin la Pi: GND de arriba y GND de abajo suenan entre sí.",
              "Con la Pi encendida: 3,3 V en el riel morado y ~5 V en el rojo, en ambas mitades."],
    "leds": ["Modo diodo sobre cada LED: marca solo con la punta roja en la pata larga.",
             "Con la Pi: GPIO22 enciende el verde y GPIO23 el amarillo."],
    "panic": ["Sin la Pi: físico 18 a GND no suena en reposo y suena al pulsar.",
              "Sin la Pi: físico 18 a 3V3 marca ~10 kΩ (R12), nunca continuidad.",
              "Con la Pi: gpio-monitor muestra panic_pressed al pulsar."],
    "tx": ["Sin la Pi, modo diodo en Q1 (C–B–E): base→emisor y base→colector ~0,6–0,7 V; al revés, nada.",
           "Modo diodo en D1: ~1,1–1,3 V con la punta roja en el ánodo.",
           "Con TX en alto 20 s: base de Q1 ~0,7 V, caída en R1 ~3 V, D1 ~1,2–1,4 V.",
           "Cámara frontal en penumbra a 5–10 cm: D1 se ve como un punto morado."],
    "rx": ["Sin la Pi: RV1 de extremo a extremo ~10 kΩ fijos; el cursor cambia al girar.",
           "Con la Pi: VBIAS ~2,1–2,3 V, U1.8 ~5 V, OPT_RX entre 0 y 3,3 V (nunca 5 V).",
           "SENSE baja al iluminar Q2 con luz IR. Ajusta RV1 entre SENSE en oscuridad y con luz.",
           "gpio-monitor: light pasa a 1 con luz y a 0 en oscuridad; si es al revés, usa --rx-inverted."],
}


def page(layout, svg, alt):
    stage_html = []
    for stage, label in STAGES.items():
        rows = []
        for p in (x for x in layout.parts if x["stage"] == stage):
            spots = ", ".join(f"{k} {spot(layout, h)}" for k, h in p["pins"].items())
            rows.append(f'<li><label><input type="checkbox"> <b>{p["ref"]}</b> {esc(p["value"])}: {spots}</label></li>')
        for w in (x for x in layout.wires if x["stage"] == stage):
            rows.append(f'<li><label><input type="checkbox"> <b>{w["id"]}</b> {spot(layout, w["a"])} ↔ '
                        f'{spot(layout, w["b"])} · {esc(w["why"])}</label></li>')
        checks = "".join(f"<li>{esc(c)}</li>" for c in STAGE_CHECKS[stage])
        stage_html.append(f'<section class="card" id="stage-{stage}"><h3>{label}</h3>'
                          f'<ul class="steps">{"".join(rows)}</ul>'
                          f'<h4>Comprueba antes de seguir</h4><ol>{checks}</ol></section>')
    pi_rows = [[n, esc(PI_PINS[n][2]), esc(PI_PINS[n][3]), esc(PI_PINS[n][4]),
                "<code>" + next(w["b"] for w in layout.wires if w["a"] == f"PI:{n}") + "</code>"]
               for n in sorted(PI_PINS)]
    bom = collections.defaultdict(list)
    for p in layout.parts:
        bom[p["value"]].append(p["ref"])
    bom_rows = [[esc(v), len(refs), ", ".join(refs)] for v, refs in bom.items()]
    bom_rows.append(["Jumpers", len(layout.wires), f"W01–W{len(layout.wires):02d}"])
    fj = sorted((h for h in layout.claims if on_fj(h)), key=lambda h: (int(h[1:]), h[0]))
    fj_rows = [[f"<code>{h}</code>", esc(layout.claims[h]),
                esc(FJ_LANDMARKS[layout.owner(h)["landmark"]])] for h in fj]
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FaroNet protoboard rev. {REVISION}</title><style>{PAGE_CSS}</style></head><body><main>
<header><p class="kicker">FARONET · HARDWARE · REVISIÓN {REVISION}</p><h1>Un Faro por protoboard, sin RGB.</h1>
<p>Mismo circuito básico de la revisión 6: mismos componentes, valores, redes y pines de la Pi. Cambia
dónde va cada pieza. RGB, R13–R15 y GPIO5/6/13 quedan fuera del diseño.</p></header>
<section class="card"><h2>Por qué cambió la colocación</h2><ul>
<li><b>La numeración de F–J está invertida en el tablero del equipo.</b> Casi todo va en la mitad A–E.
Solo usan F–J las patas del botón, las tiras debajo del LM393 y el emisor IR en el borde derecho.
Esos agujeros se ubican por referencia física, no por el número impreso.</li>
<li><b>Emisor y receptor en filas espejo.</b> D1 en la fila h y Q2 en la c: al girar el segundo Faro 180°
quedan a la misma altura exacta.</li>
<li><b>Bloques de izquierda a derecha:</b> LEDs, pánico, receptor y emisor, cada uno con su GPIO.</li>
<li><b>RV1 apartado del LM393,</b> con espacio libre alrededor y su ranura de ajuste accesible.</li>
<li><b>Errores ya vistos que el validador rechaza:</b> Q1 invertido, D1 invertido, botón girado y clips
que unen redes.</li>
<li>{len(layout.wires)} jumpers en lugar de 35. Ningún agujero ocupado queda bajo el cuerpo de una pieza.</li>
</ul></section>
<section class="card"><h2>Plano</h2><p>Haz clic en un agujero, pin o cable para resaltar su red.
Los números de columna son los de la mitad A–E.</p>
<div class="tools"><input id="search" placeholder="Buscar agujero, pieza o red (p. ej. d60, R6, SENSE)">
<button id="clear" type="button">Quitar resaltado</button><span id="found"></span></div>
<div class="svgwrap" id="plan">{svg}</div></section>
<section class="card"><h2>Pines de la Pi</h2>{table(["Físico", "Señal", "Red", "Función", "Destino"], pi_rows)}
<p>Pi 2 Model B v1.1 y Pi 3 Model B usan el mismo header de 40 pines. Solo se usan estos ocho pines.</p></section>
<section class="card"><h2>Piezas por Faro</h2>{table(["Pieza", "Cantidad", "Referencias"], bom_rows)}</section>
<section class="card"><h2>Orientación de piezas con polaridad</h2><ul>
<li><b>Q1 2N2222:</b> C–B–E: mirando su cara plana, patas de izquierda a derecha colector, base y emisor.
Va en d59–d60–d61 con la cara plana hacia el canal central. Confirma la base con el modo diodo antes de insertarlo.</li>
<li><b>D1 LED IR:</b> ánodo (pata larga) en h62 y cátodo en h63; lente hacia la derecha, fuera del tablero.</li>
<li><b>Q2 PT333:</b> emisor (pata larga, pin 1) en c62 y colector en c63; lente hacia la derecha.</li>
<li><b>D2 y D3:</b> pata larga en el tablero (c7 y c14), pata corta en el riel GND de arriba.</li>
<li><b>U1 LM393:</b> muesca hacia la derecha. El pin 1 queda en {spot(layout, layout.pins("U1")["1 OUT1"])}
y el pin 8 justo debajo, en la mitad F–J.</li>
<li><b>C1 100 µF:</b> franja (−) en el riel GND de abajo; + en el riel de 5 V.</li>
<li><b>S1:</b> cada pareja unida internamente (1–2 y 3–4) cruza el canal. En reposo e18 y e20 no suenan;
al pulsar, sí.</li>
<li><b>RV1:</b> trimpot vertical RM063 con extremos en {spot(layout, layout.pins("RV1")["1 extremo"])} y
{spot(layout, layout.pins("RV1")["3 extremo"])} y cursor en {spot(layout, layout.pins("RV1")["2 cursor"])}. La ranura
de ajuste (donde entra el destornillador) mira hacia el canal central; la fila e frente a ella queda libre.
Si es el horizontal RM065, el cursor va en <code>{alt.pins("RV1")["2 cursor"]}</code>, que queda libre para eso.</li>
</ul></section>
<section class="card"><h2>Agujeros de la mitad F–J</h2><p>Son los únicos. Si un agujero de F–J no está en
esta tabla, debe quedar vacío.</p>{table(["Agujero (modelo)", "Ocupado por", "Cómo encontrarlo"], fj_rows)}</section>
<h2 class="section">Montaje por etapas</h2><p>Monta y comprueba una etapa a la vez. Haz las pruebas de
continuidad <b>sin alimentación</b> y con la Pi desconectada.</p>
{"".join(stage_html)}
<section class="card"><h2>Dos Faros enfrentados</h2><div class="svgwrap">{facing_svg()}</div>
<p>Arma los dos Faros con el mismo plano y gira el segundo protoboard 180°.</p></section>
<section class="card"><h2>Límites</h2><p>El validador comprueba continuidad del modelo, una pieza por
agujero y la regla de F–J. No acredita funcionamiento analógico, alcance, velocidad ni BER. Las
orientaciones físicas de Q1, Q2, D1, S1 y RV1 se comprueban con el multímetro antes de conectar la Pi.</p></section>
</main><script>{PAGE_JS}</script></body></html>'''


PAGE_CSS = (
    ":root{color-scheme:light;--ink:#1c2b36;--muted:#546e7a;--line:#d5dee5;--bg:#eef2f5}"
    "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,sans-serif}"
    "main{max-width:1180px;margin:0 auto;padding:24px 16px 60px}h1{font-size:30px;margin:4px 0 8px}"
    ".kicker{color:var(--muted);font-weight:700;letter-spacing:.06em;font-size:13px;margin:0}"
    ".card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:16px 0}"
    ".section{margin-top:32px}.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}"
    "th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}"
    "code{background:#eef2f5;border-radius:4px;padding:1px 5px}.fj{color:#a04000;font-size:13px}"
    ".svgwrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px}.svgwrap svg{display:block;max-width:none}"
    ".steps{list-style:none;padding:0}.steps li{padding:4px 0;border-bottom:1px dashed var(--line)}"
    ".tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}"
    ".tools input{flex:1 1 260px;padding:8px;border:1px solid var(--line);border-radius:6px;font:inherit}"
    ".tools button{padding:8px 12px;border-radius:6px;border:1px solid var(--line);background:#fff;font:inherit}"
    "svg .dim{opacity:.15}svg .hit{stroke:#ff1744;stroke-width:2.5}"
    "@media (max-width:600px){h1{font-size:24px}.card{padding:14px}}"
)

PAGE_JS = r"""
const plan=document.getElementById('plan'),found=document.getElementById('found');
function clear(){plan.querySelectorAll('.dim,.hit').forEach(e=>e.classList.remove('dim','hit'));found.textContent='';}
function highlight(net,item){clear();let n=0;
 plan.querySelectorAll('.hole,.pin,.jumper,.part').forEach(e=>{
  const match=(net&&e.dataset.net===net)||(item&&[e.dataset.hole,e.dataset.ref,e.dataset.id].includes(item));
  e.classList.toggle('dim',!match);if(match&&e.matches('.hole,.pin')){e.classList.add('hit');n++;}});
 found.textContent=net?`Red ${net}: ${n} puntos`:'';}
plan.addEventListener('click',e=>{const t=e.target.closest('[data-net]');if(t&&t.dataset.net)highlight(t.dataset.net);});
document.getElementById('clear').addEventListener('click',()=>{clear();document.getElementById('search').value='';});
document.getElementById('search').addEventListener('input',e=>{const q=e.target.value.trim();if(!q)return clear();
 const hole=plan.querySelector(`[data-hole="${CSS.escape(q)}"]`);
 if(hole&&hole.dataset.net)return highlight(hole.dataset.net,q);
 const nets=new Set([...plan.querySelectorAll('[data-net]')].map(x=>x.dataset.net));
 highlight([...nets].find(x=>x&&x.toLowerCase()===q.toLowerCase()),q.toUpperCase());});
"""


def export_data(layout):
    return {
        "revision": REVISION,
        "numbering": "Columns follow the A–E half; F–J holes are located by landmark.",
        "parts": layout.parts, "wires": layout.wires,
        "occupied": sorted(layout.claims), "hole_nets": dict(sorted(layout.hole_nets.items())),
        "fj_landmarks": FJ_LANDMARKS,
    }


def export(layout):
    svg = Drawing(layout).draw()
    (HERE / "faronet-breadboard.svg").write_text(svg + "\n")
    (HERE / "faronet-facing-layout.svg").write_text(facing_svg() + "\n")
    (HERE / "layout-data.json").write_text(json.dumps(export_data(layout), ensure_ascii=False, indent=1) + "\n")
    (HERE / "faronet-breadboard-review.html").write_text(page(layout, svg, make("RM065")) + "\n")


LAYOUT = make()

if __name__ == "__main__":
    export(LAYOUT)
    print("Validated:", len(LAYOUT.claims), "terminals,", len(LAYOUT.wires), "jumpers,",
          len(LAYOUT.parts), "parts")
