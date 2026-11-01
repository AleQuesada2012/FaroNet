"""Draw the perfboard layout: component side and copper side, as standalone SVG.

Both views come from layout.make(), which check.py has already validated.
The component side is what you see while inserting parts (printed numbers on
top). The copper side is the same board flipped top-to-bottom, as you see it
while soldering: row 1 at the bottom, columns still left to right.
"""

from html import escape
import math

from board import COLS, PAIRS, RAILS, ROWS

P = 24                     # px per 2.54 mm
X0, Y0 = 330, 70           # centre of column 1, row 1
NET_COLOR = {
    "5V": "#d32f2f", "3V3": "#8e44ad", "GND": "#37474f", "TX": "#1565c0",
    "OPT_RX": "#00838f", "LED_TX": "#2e7d32", "LED_RX": "#b8860b",
    "PANIC": "#c2185b", "VBIAS": "#a1887f", "VTH": "#6d4c41", "SENSE": "#ef6c00",
    "Q_BASE": "#3949ab", "IR_A": "#e57373", "IR_K": "#795548",
    "GREEN_A": "#43a047", "YELLOW_A": "#fbc02d",
}
RAIL_NET = {7: "GND", 14: "3V3", 21: "5V", 28: "GND"}
WIDTH = X0 + 37 * P
HEIGHT = Y0 + 27 * P


def color(net):
    return NET_COLOR.get(net, "#555")


class View:
    def __init__(self, copper: bool):
        self.copper = copper
        self.out = []

    def xy(self, r, c):
        row = (ROWS + 1 - r) if self.copper else r
        return X0 + (c - 1) * P, Y0 + (row - 1) * P

    def add(self, s):
        self.out.append(s)

    def text(self, x, y, s, size=11, anchor="middle", fill="#fff", weight="normal", cls=""):
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
                 f'fill="{fill}" font-weight="{weight}" class="{cls}">{escape(str(s))}</text>')

    def poly(self, pts, stroke, width, dash="", cap="round", opacity=1.0):
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" '
                 f'stroke-linecap="{cap}" stroke-linejoin="round" opacity="{opacity}"{extra}/>')

    # --- board ----------------------------------------------------------
    def board(self):
        left, top = X0 - 2.3 * P, Y0 - 2.0 * P
        w, h = 35.4 * P, 27.6 * P
        self.add(f'<rect x="{left}" y="{top}" width="{w}" height="{h}" rx="10" fill="#1d4f9c" '
                 f'stroke="#0f2f63" stroke-width="2"/>')
        big_row = 25.6 if not self.copper else -0.6
        for c in (1.5, 3.4, 5.3, 7.2, 9.1, 11, 21.5, 23.4, 25.3, 27.2, 29.1, 31):
            x, y = X0 + (c - 1) * P, Y0 + (big_row - 1) * P
            self.add(f'<circle cx="{x}" cy="{y}" r="6" fill="#0b1f40" stroke="#c9d3e0" stroke-width="2"/>')
        for c in range(1, COLS + 1):
            x, y = self.xy(1, c)
            ty = Y0 - 1.15 * P if not self.copper else Y0 + ROWS * P + 0.2 * P
            self.text(x, ty, f"{c:03d}", size=9, fill="#e3ecf8")
        for r in range(1, ROWS + 1):
            x, y = self.xy(r, 1)
            self.text(X0 - 1.6 * P, y + 4, f"F{r}", size=9, fill="#e3ecf8", anchor="end")
        if self.copper:
            for c in RAILS:
                x1, y1 = self.xy(1, c)
                x2, y2 = self.xy(ROWS, c)
                self.add(f'<rect x="{x1 - 7}" y="{min(y1, y2) - 9}" width="14" height="{abs(y2 - y1) + 18}" '
                         f'rx="7" fill="#c8ccd2"/>')
            for r in range(1, ROWS + 1):
                for a, b in PAIRS:
                    xa, y = self.xy(r, a)
                    xb, _ = self.xy(r, b)
                    self.add(f'<rect x="{xa - 9}" y="{y - 8}" width="{xb - xa + 18}" height="16" rx="8" fill="#c8ccd2"/>')
            for r in range(1, ROWS + 1):
                for c in range(1, COLS + 1):
                    x, y = self.xy(r, c)
                    self.add(f'<circle cx="{x}" cy="{y}" r="3.2" fill="#0b1f40"/>')
        else:
            for c in RAILS:
                x1, y1 = self.xy(1, c)
                x2, y2 = self.xy(ROWS, c)
                self.add(f'<rect x="{x1 - 8}" y="{y1 - 10}" width="16" height="{y2 - y1 + 20}" rx="8" '
                         f'fill="none" stroke="{color(RAIL_NET[c])}" stroke-width="2.5" stroke-dasharray="4 3" opacity="0.9"/>')
            for r in range(1, ROWS + 1):
                for c in range(1, COLS + 1):
                    x, y = self.xy(r, c)
                    self.add(f'<circle cx="{x}" cy="{y}" r="3.4" fill="#0b1f40" stroke="#5f86c4" stroke-width="1"/>')
        for c, net in RAIL_NET.items():
            x, _ = self.xy(1, c)
            y = Y0 - 1.75 * P if not self.copper else Y0 + ROWS * P + 0.95 * P
            self.add(f'<rect x="{x - 19}" y="{y - 11}" width="38" height="15" rx="4" fill="{color(net)}"/>')
            self.text(x, y + 1, f"C{c} {net}", size=9, weight="bold")

    # --- component side -------------------------------------------------
    def leads_and_wires(self, L):
        for w in L.wires:
            pts = [self.xy(*w["a"])] + [self.xy(r, c) for r, c in w["via"]] + [self.xy(*w["b"])]
            self.poly(pts, "#fff", 7)
            self.poly(pts, color(w["net"]), 4.5)
            for h in (w["a"], w["b"]):
                x, y = self.xy(*h)
                self.add(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{color(w["net"])}" stroke="#fff" stroke-width="1.5"/>')
        # Stack the Pi labels at least 20 px apart, each joined to its own lead.
        starts = sorted((self.xy((l["via"][0] if l["via"] else l["hole"])[0], 1)[1], i)
                        for i, l in enumerate(L.pi))
        label_y, last = {}, -1e9
        for y, i in starts:
            last = max(y, last + 20)
            label_y[i] = last
        for index, lead in enumerate(L.pi):
            start = lead["via"][0] if lead["via"] else (lead["hole"][0], 0)
            pts = [(X0 - 6.2 * P, self.xy(start[0], 1)[1])]
            pts += [self.xy(r, c) if c else (X0 - 2.6 * P, self.xy(r, 1)[1]) for r, c in lead["via"]]
            pts.append(self.xy(*lead["hole"]))
            if not lead["via"]:
                pts.insert(1, (X0 - 2.6 * P, pts[-1][1]))
            self.poly(pts, color(lead["net"]), 3, dash="7 4")
            x, y = self.xy(*lead["hole"])
            self.add(f'<circle cx="{x}" cy="{y}" r="5" fill="#fff" stroke="{color(lead["net"])}" stroke-width="3"/>')
            label = f"Pi {lead['physical']} · {lead['net']}"
            lx, ly = pts[0]
            if label_y[index] != ly:
                self.poly([(lx - 2, label_y[index]), (lx + 6, label_y[index]), (lx + 14, ly)],
                          color(lead["net"]), 2)
                ly = label_y[index]
            self.add(f'<rect x="{lx - 86}" y="{ly - 9}" width="84" height="16" rx="4" fill="{color(lead["net"])}"/>')
            self.text(lx - 44, ly + 3, label, size=10, weight="bold")

    def resistor(self, p, a, b):
        (xa, ya), (xb, yb) = self.xy(*a), self.xy(*b)
        dist = math.hypot(xb - xa, yb - ya)
        label = p["value"].replace(" ", "")
        if dist < 1.5 * P:  # standing: body on pin 1, lead arching to pin 2
            self.add(f'<path d="M{xa},{ya} Q{(xa + xb) / 2 + 10},{(ya + yb) / 2} {xb},{yb}" fill="none" '
                     f'stroke="#9e9e9e" stroke-width="2"/>')
            self.add(f'<circle cx="{xa}" cy="{ya}" r="10" fill="#e8cfa0" stroke="#7a5c2e" stroke-width="1.5"/>')
            self.text(xa, ya + 3.5, p["ref"], size=9, fill="#3b2a12", weight="bold")
            right = a[1] >= 26
            self.text(xa + (13 if right else -13), ya + 4, label, size=9, fill="#fff",
                      anchor="start" if right else "end", cls="halo")
            self.add(f'<circle cx="{xb}" cy="{yb}" r="2.2" fill="#ffeb3b"/>')
            return True
        self.poly([(xa, ya), (xb, yb)], "#9e9e9e", 2)
        ang = math.degrees(math.atan2(yb - ya, xb - xa))
        length = min(dist - 0.7 * P, 2.7 * P)
        cx, cy = (xa + xb) / 2, (ya + yb) / 2
        self.add(f'<g transform="translate({cx:.1f},{cy:.1f}) rotate({ang:.1f})">'
                 f'<rect x="{-length / 2:.1f}" y="-7" width="{length:.1f}" height="14" rx="6" fill="#e8cfa0" '
                 f'stroke="#7a5c2e" stroke-width="1.5"/></g>')
        self.text(cx, cy + 3.5, f"{p['ref']} {label}", size=8.5, fill="#3b2a12", weight="bold")

    def part(self, p):
        ref, pins = p["ref"], p["pins"]
        pts = {k: self.xy(*h) for k, h in pins.items()}
        if ref.startswith("R") and ref != "RV1":
            if self.resistor(p, pins["1"], pins["2"]):
                return
        elif ref in ("D2", "D3"):
            (xa, ya), (xk, yk) = pts["A"], pts["K"]
            fill = "#66bb6a" if ref == "D2" else "#fdd835"
            cx, cy = (xa + xk) / 2, (ya + yk) / 2
            self.add(f'<circle cx="{cx}" cy="{cy}" r="{P * 0.95}" fill="{fill}" stroke="#222" stroke-width="1.5" opacity="0.92"/>')
            self.add(f'<line x1="{xk + 5}" y1="{cy - 18}" x2="{xk + 5}" y2="{cy + 18}" stroke="#222" stroke-width="2"/>')
            self.text(cx, cy + 4, ref, size=10, fill="#111", weight="bold")
            self.text(xa - 2, ya - 13, "A", size=9, fill="#fff", cls="halo")
            self.text(xk + 2, yk - 13, "K", size=9, fill="#fff", cls="halo")
        elif ref in ("D1", "Q2"):
            (x1, y1), (x2, y2) = list(pts.values())
            edge = X0 + 33.1 * P
            for x, y in (pts.values()):
                self.poly([(x, y), (edge + 8, y)], "#bdbdbd", 2)
            cy = (y1 + y2) / 2
            fill = "#b39ddb" if ref == "D1" else "#212121"
            self.add(f'<path d="M{edge + 8},{cy - 13} h{2.2 * P} a13,13 0 0 1 0,26 h-{2.2 * P} z" fill="{fill}" '
                     f'stroke="#111" stroke-width="1.5"/>')
            self.add(f'<rect x="{edge + 4}" y="{cy - 15}" width="7" height="30" fill="#111" opacity="0.85"/>')
            name = "D1 IR" if ref == "D1" else "Q2 PT333"
            self.text(edge + 8 + 1.3 * P, cy + 4, name, size=9, fill="#fff" if ref == "Q2" else "#111", weight="bold")
            for k, (x, y) in pts.items():
                self.text(x, y - 9, k, size=9, fill="#fff", cls="halo")
        elif ref == "Q1":
            # The team's 2N2222 reads E-B-C facing the flat side (transistor tester),
            # so with C on top the flat face points left, toward R2.
            (xc, yc), (xb, yb), (xe, ye) = pts["C"], pts["B"], pts["E"]
            self.add(f'<path d="M{xb - 9},{yc - 12} L{xb - 9},{ye + 12} A30,30 0 0 0 {xb - 9},{yc - 12} z" '
                     f'fill="#263238" stroke="#000" stroke-width="1.5" opacity="0.92"/>')
            self.add(f'<line x1="{xb - 9}" y1="{yc - 12}" x2="{xb - 9}" y2="{ye + 12}" stroke="#ffeb3b" stroke-width="3"/>')
            for k, (x, y) in pts.items():
                self.add(f'<circle cx="{x}" cy="{y}" r="3" fill="#bbb"/>')
                self.text(x + 11, y + 4, k, size=9, fill="#fff", weight="bold")
            self.text(xb - 14, yc + 4, "Q1", size=10, fill="#fff", weight="bold", anchor="end", cls="halo")
        elif ref == "U1":
            xs = [x for x, _ in pts.values()]
            ys = [y for _, y in pts.values()]
            x1, x2, y1, y2 = min(xs) - 9, max(xs) + 9, min(ys) - 12, max(ys) + 12
            self.add(f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" rx="3" fill="#212121" stroke="#000"/>')
            notch_y = y2 if not self.copper else y1
            self.add(f'<path d="M{(x1 + x2) / 2 - 8},{notch_y} a8,8 0 0 {0 if not self.copper else 1} 16,0" fill="#1d4f9c"/>')
            for k, (x, y) in pts.items():
                self.add(f'<rect x="{x - 4}" y="{y - 4}" width="8" height="8" fill="#cfd8dc"/>')
                n = k.split()[0]
                self.text(x + (-14 if x == min(xs) else 14), y + 4, n, size=9, fill="#fff", weight="bold")
            self.text((x1 + x2) / 2, (y1 + y2) / 2 - 2, "U1", size=11, weight="bold")
            self.text((x1 + x2) / 2, (y1 + y2) / 2 + 11, "LM393", size=8)
        elif ref == "C1":
            (xp, yp), (xm, ym) = pts["+"], pts["−"]
            body_l, body_r = xp - 4.6 * P, xp - 0.6 * P
            self.poly([(xp, yp), (body_r, yp)], "#bdbdbd", 2)
            self.poly([(xm, ym), (xm, ym - 9), (body_r, ym - 9)], "#bdbdbd", 2)
            self.add(f'<rect x="{body_l}" y="{yp - 15}" width="{body_r - body_l}" height="30" rx="7" fill="#1e3a8a" stroke="#000"/>')
            self.add(f'<rect x="{body_l + 4}" y="{yp - 15}" width="9" height="30" fill="#cfd8dc" opacity="0.8"/>')
            self.text((body_l + body_r) / 2 + 4, yp + 4, "C1 100µF (acostado)", size=8.5, weight="bold")
            self.text(xp, yp - 11, "+", size=13, fill="#fff", weight="bold", cls="halo")
            self.text(xm + 2, ym + 18, "−", size=13, fill="#fff", weight="bold", cls="halo")
        elif ref in ("C2", "C3"):
            (x1, y1), (x2, y2) = pts["1"], pts["2"]
            self.poly([(x1, y1), (x2, y2)], "#bdbdbd", 2)
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            self.add(f'<ellipse cx="{cx}" cy="{cy - 2}" rx="13" ry="9" fill="#e6a23c" stroke="#7a4b00" stroke-width="1.5"/>')
            self.text(cx, cy + 1.5, ref, size=8.5, fill="#3b2a00", weight="bold")
        elif ref == "S1":
            xs = [x for x, _ in pts.values()]
            ys = [y for _, y in pts.values()]
            cx, cy = sum(xs) / 4, sum(ys) / 4
            self.add(f'<rect x="{cx - 29}" y="{cy - 29}" width="58" height="58" rx="5" fill="#424242" stroke="#000"/>')
            self.add(f'<circle cx="{cx}" cy="{cy}" r="14" fill="#c62828"/>')
            self.text(cx, cy + 4, "S1", size=10, weight="bold")
            for k, (x, y) in pts.items():
                self.add(f'<circle cx="{x}" cy="{y}" r="3.5" fill="#bbb"/>')
                self.text(x + (-10 if x < cx else 10), y + 4, k, size=9, fill="#fff", weight="bold")
        elif ref == "RV1":
            xs = [x for x, _ in pts.values()]
            ys = [y for _, y in pts.values()]
            self.add(f'<rect x="{min(xs) - 12}" y="{min(ys) - 12}" width="{max(xs) - min(xs) + 24}" '
                     f'height="{max(ys) - min(ys) + 24}" rx="4" fill="#1565c0" stroke="#0d3c78"/>')
            cx, cy = sum(xs) / 3, sum(ys) / 3
            self.add(f'<circle cx="{cx}" cy="{cy}" r="7" fill="#eceff1"/>'
                     f'<line x1="{cx - 5}" y1="{cy}" x2="{cx + 5}" y2="{cy}" stroke="#333" stroke-width="2"/>')
            self.text(min(xs) - 16, cy + 4, "RV1 10k", size=9, fill="#fff", anchor="end", cls="halo")
        for k, (x, y) in pts.items():
            self.add(f'<circle cx="{x}" cy="{y}" r="2.2" fill="#ffeb3b"/>')

    # --- copper side ----------------------------------------------------
    def copper_marks(self, L):
        for l in L.links:
            (xa, ya), (xb, yb) = self.xy(*l["a"]), self.xy(*l["b"])
            self.poly([(xa, ya), (xb, yb)], "#ffffff", 8)
            self.poly([(xa, ya), (xb, yb)], color(l["net"]), 5)
        for h, owner in L.used.items():
            x, y = self.xy(*h)
            self.add(f'<circle cx="{x}" cy="{y}" r="6" fill="#8d99a6" stroke="#2b2f35" stroke-width="1.5"/>')
            short = owner.replace("cable ", "").replace("Pi ", "Pi")
            if owner.startswith("U1."):
                short = owner.split(".")[1].split()[0]
            self.text(x, y - 9, short[:7], size=7.5, fill="#fff", cls="halo")

    def svg(self, L, title):
        self.board()
        if self.copper:
            self.copper_marks(L)
        else:
            self.leads_and_wires(L)
            for p in sorted(L.parts, key=lambda p: p["ref"] in ("U1", "S1", "RV1")):
                self.part(p)
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT + 40}" '
                f'font-family="Inter, Helvetica, Arial, sans-serif" role="img">'
                f'<title>{escape(title)}</title>'
                '<style>.halo{paint-order:stroke;stroke:#0b1f40;stroke-width:3px}</style>'
                f'<rect width="100%" height="100%" fill="#f4f6f9"/>')
        self.text(16, HEIGHT + 24, title, size=14, fill="#1b2a3a", anchor="start", weight="bold")
        return head + "".join(self.out) + "</svg>"


def component_svg(L):
    return View(copper=False).svg(L, "Lado de componentes (lado impreso, números arriba)")


def copper_svg(L):
    return View(copper=True).svg(
        L, "Lado de cobre (placa volteada de arriba abajo: F1 abajo). Líneas de color = puentes de cobre")
