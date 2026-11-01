"""Build the soldering guide (guia.html), both SVG views and soldering-sheet.md.

Run `python3 guide.py` from this folder. It validates the layout first
(check.py), so nothing is written for a layout that breaks the netlist.
"""

from collections import defaultdict
from html import escape

from board import HERE, name
import check
import render

STAGES = {
    "power": ("1 · Alimentación y puentes de GND",
              "Rieles: C7 y C28 son GND, C14 es 3V3, C21 es 5V. Márcalos con marcador en el "
              "lado impreso antes de empezar. C1 es electrolítico: la pata larga (+) va al riel "
              "de 5 V (C21) y el cuerpo se acuesta hacia la izquierda."),
    "leds": ("2 · LED verde y amarillo",
             "Pata larga (ánodo, A) a la izquierda; la cara plana (cátodo, K) sobre el riel C7."),
    "panic": ("3 · Botón de pánico",
              "S1 queda a caballo del riel C7: las patas unidas 1–2 a la izquierda (C6), 3–4 a "
              "la derecha (C8). Comprueba con el multímetro qué patas están unidas en reposo "
              "antes de soldar: deben quedar 1 sobre 2 en la misma columna."),
    "tx": ("4 · Emisor IR",
           "D1 sale por el borde derecho: dobla las patas 90° justo detrás del cuerpo para que el "
           "LED quede fuera de la placa. Ánodo (pata larga) en F4, cátodo en F5. Q1 con la cara "
           "plana hacia el borde derecho: C arriba (F5), B (F6), E abajo (F7). R1 va acostada "
           "con patas largas de C21 a C29."),
    "rx": ("5 · Receptor",
           "Suelda el zócalo DIP8 con la muesca hacia abajo (hacia F24); el LM393 se pone al "
           "final. Q2 sale por el borde derecho como D1: colector en F20, emisor (pata larga "
           "según Everlight) en F21. El bus VBIAS es un alambre desnudo por el lado de cobre a "
           "lo largo de C24, de F13 a F23; no debe tocar la fila F12 (GND)."),
}

ISOLATION = [
    ("5V (C21)", "GND (C7)", "No pita. Sube despacio (C1 cargándose) hasta más de 100 kΩ."),
    ("3V3 (C14)", "GND (C7)", "≈ 2,5–2,9 kΩ (R8 más R9 en paralelo con RV1)."),
    ("5V (C21)", "3V3 (C14)", "Abierto (más de 100 kΩ)."),
    ("VBIAS (F21·C24)", "GND (C28)", "≈ 1,8 kΩ (R9 en paralelo con RV1)."),
    ("OPT_RX (F15·C27)", "3V3 (C14)", "≈ 4,3–4,7 kΩ (R5)."),
    ("PANIC (F13·C9)", "GND (C7)", "Abierto; con S1 pulsado, menos de 1 Ω."),
    ("Q_BASE (F6·C29)", "GND (C28)", "≈ 10 kΩ (R3); en un sentido puede marcar menos por el diodo B–E."),
    ("GND C7", "GND C28", "Pita (< 1 Ω). Quita un puente de GND a la vez: debe seguir pitando."),
]


def terminals_by_net(plan):
    nets = defaultdict(list)
    for h, net, label in plan.terminals():
        if net != "NC_U1_7":
            nets[net].append((label, h))
    return nets


def stage_rows(plan, stage):
    rows = []
    for p in plan.parts:
        if p["stage"] == stage:
            pins = ", ".join(f"{pin.split()[0]} → {name(h)}" for pin, h in p["pins"].items())
            rows.append((f"{p['ref']} · {p['value']}", pins, "pieza"))
    for w in plan.wires:
        if w["stage"] == stage:
            rows.append((f"Cable aislado {w['net']}", f"{name(w['a'])} ↔ {name(w['b'])}", "cable"))
    for l in plan.links:
        if l["stage"] == stage:
            rows.append((f"Puente de cobre {l['net']}", f"{name(l['a'])} ↔ {name(l['b'])}", "cobre"))
    for lead in plan.pi:
        if lead["stage"] == stage:
            rows.append((f"Cable de la Pi · pin {lead['physical']} ({lead['net']})",
                         name(lead["hole"]), "pi"))
    return rows


def markdown(plan, caught):
    out = ["# Hoja de soldadura (generada por `guide.py`)", "",
           "F = fila 1–24 desde el borde con los números impresos; C = columna 1–32 impresa.",
           "Rieles: C7 GND, C14 3V3, C21 5V, C28 GND. Piezas por el lado impreso; se suelda",
           "por el lado de cobre. «Puente de cobre» = alambre desnudo o pata cortada entre dos",
           "pads vecinos del lado de cobre (no ocupa agujero). La guía con dibujos es `guia.html`.", ""]
    for stage, (title, _) in STAGES.items():
        out += [f"## {title}", "", "| Qué | Dónde |", "| --- | --- |"]
        out += [f"| {what} | {where} |" for what, where, _ in stage_rows(plan, stage)]
        out.append("")
    out += ["## Mapa (lado de componentes)", "", "```", plan.ascii(), "```", "",
            "Validado: todas las redes de `circuit-reference.json` unidas y sin cortos; "
            f"{len(caught)} errores típicos rechazados por `check.py`.", ""]
    return "\n".join(out)


CSS = """
:root{--bg:#f5f7fa;--fg:#1b2633;--muted:#5b6b7c;--card:#fff;--line:#d9e0e8;--accent:#1d4f9c}
@media (prefers-color-scheme:dark){:root{--bg:#10161d;--fg:#e6edf3;--muted:#9fb0c0;--card:#18212b;--line:#2a3644;--accent:#7fb0ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 Inter,system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}
h2{font-size:20px;margin:36px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:12px 0}
figure{margin:12px 0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px;overflow-x:auto}
figure svg{width:100%;min-width:760px;height:auto;display:block}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}td.where{font-family:ui-monospace,Menlo,monospace;font-size:13px}
.tag{display:inline-block;border-radius:4px;padding:0 6px;font-size:12px;margin-right:6px;color:#fff}
.pieza{background:#7a5c2e}.cable{background:#6d4c41}.cobre{background:#9aa5b1;color:#111}.pi{background:#1565c0}
label{display:flex;gap:8px;align-items:flex-start;cursor:pointer}input[type=checkbox]{margin-top:4px}
ul{padding-left:20px}code{font-family:ui-monospace,Menlo,monospace;font-size:13px}
"""


def html(plan, caught, comp_svg, copper_svg):
    nets = terminals_by_net(plan)
    parts = []
    add = parts.append
    add(f"<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Faro en perfboard</title><style>{CSS}</style></head><body><main>")
    add("<h1>Faro en perfboard · guía de soldadura</h1>")
    add("<p class='muted'>Revisión 7 en la placa azul de 7 × 9 cm del equipo (una cara de cobre, "
        "32 columnas × 24 filas, rieles en C7, C14, C21 y C28). Generada por <code>guide.py</code> "
        f"desde un plano validado contra la netlist; {len(caught)} errores típicos se rechazan "
        "automáticamente (<code>check.py</code>).</p>")
    add("<div class='card'><b>Cambios respecto a la protoboard:</b> R6 = 47 kΩ (más histéresis); "
        "R10 y R11 = 330 Ω; dos puentes de GND entre C7 y C28 (filas F1 y F24) y un segundo GND de "
        "la Pi (pin 9) al riel C28, como el puente doble de la revisión 7a; la Pi se conecta con "
        "jumpers hembra cortados: el lado hembra queda en el header de la Pi y el lado cortado se "
        "suelda a la placa.</div>")
    add("<h2>Cómo leer el plano</h2><ul>"
        "<li><b>F</b> = fila 1–24, contada desde el borde con los números impresos. "
        "<b>C</b> = columna 1–32, como está impresa. Ejemplo: <code>F15·C27</code>.</li>"
        "<li>Las piezas entran por el <b>lado impreso</b> (azul sin cobre). Se suelda por el "
        "<b>lado de cobre</b>, que es la misma placa volteada de arriba abajo: allí F1 queda abajo "
        "y las columnas siguen de izquierda a derecha.</li>"
        "<li><b>Cable aislado</b> (línea de color gruesa): alambre con forro por el lado impreso. "
        "<b>Puente de cobre</b> (línea de color en la vista de cobre): alambre desnudo o pata "
        "cortada soldada entre dos pads vecinos; no usa agujero.</li>"
        "<li>Cada pareja de agujeros de una fila ya está unida. Nunca dejes estaño entre pads "
        "vecinos que el plano no une: la placa tiene separaciones de ≈ 1 mm.</li>"
        "<li>D1 y Q2 quedan a unos 4 cm uno del otro y sus filas centrales suman 25: un segundo "
        "Faro girado 180° queda con su emisor frente a tu receptor. Pon funda negra "
        "(termoencogible o cinta) alrededor del cuerpo de D1 y de Q2 para que la luz lateral del "
        "emisor y la del cuarto no lleguen al receptor.</li></ul>")
    add("<h2>Lado de componentes</h2><figure>" + comp_svg + "</figure>")
    add("<p class='muted'>Líneas punteadas: jumpers de la Pi (entran por la izquierda; átalos con "
        "una brida a dos agujeros grandes del borde inferior para que no tiren de la soldadura). "
        "Rieles marcados con línea punteada de su color. Las resistencias de pie se dibujan como "
        "un círculo con la pata que vuelve.</p>")
    add("<h2>Lado de cobre</h2><figure>" + copper_svg + "</figure>")
    add("<h2>Montaje por etapas</h2><p class='muted'>Haz una etapa completa, revisa sus puentes de "
        "cobre y prueba su continuidad antes de pasar a la siguiente. Marca cada fila al terminar.</p>")
    for stage, (title, note) in STAGES.items():
        add(f"<h3>{escape(title)}</h3><p>{escape(note)}</p><table><tr><th></th><th>Qué</th><th>Dónde</th></tr>")
        for what, where, kind in stage_rows(plan, stage):
            add(f"<tr><td><input type='checkbox'></td><td><span class='tag {kind}'>{kind}</span>"
                f"{escape(what)}</td><td class='where'>{escape(where)}</td></tr>")
        add("</table>")
    add("<h2>Pruebas sin energía</h2><p>Pi desconectada y <b>sin el LM393</b> en el zócalo. "
        "Multímetro en continuidad: cada grupo debe pitar entre su primer punto y todos los demás.</p>"
        "<table><tr><th>Red</th><th>Puntos (deben pitar entre sí)</th></tr>")
    for net in sorted(nets):
        points = ", ".join(f"{label} {name(h)}" for label, h in nets[net])
        add(f"<tr><td><b>{escape(net)}</b></td><td class='where'>{escape(points)}</td></tr>")
    add("</table><p>Aislamiento (multímetro en Ω):</p><table><tr><th>Entre</th><th>y</th><th>Esperado</th></tr>")
    for a, b, expected in ISOLATION:
        add(f"<tr><td class='where'>{escape(a)}</td><td class='where'>{escape(b)}</td><td>{escape(expected)}</td></tr>")
    add("</table>")
    add("<h2>Primer encendido</h2><ol>"
        "<li>Con el LM393 aún fuera, conecta los jumpers a la Pi (pines físicos 1, 2, 6, 9, 11, 13, "
        "15, 16 y 18) y enciéndela. Mide contra C7: C21 ≈ 5 V, C14 ≈ 3,3 V, VBIAS (F21·C24) ≈ 2,1 V.</li>"
        "<li>Apaga la Pi. Inserta el LM393 con la muesca hacia abajo (pin 1 en F15·C26). Enciende "
        "y mide OPT_RX (F15·C27): siempre entre 0 y 3,3 V.</li>"
        "<li>En la Pi, desde <code>~/FaroNet/python</code>:<br>"
        "<code>sudo .venv/bin/python -m faronet gpio-preflight</code><br>"
        "<code>sudo .venv/bin/python -m faronet gpio-calibrate --hardware-ready --blink</code> "
        "(ajusta RV1 con papel blanco sobre D1 y Q2)<br>"
        "<code>sudo .venv/bin/python -m faronet optical-loopback --hardware-ready --count 10 --half-bit-ms 2</code></li>"
        "<li>Prueba el botón de pánico durante <code>gpio-calibrate</code>: debe detenerlo con "
        "todas las salidas apagadas.</li></ol>")
    add("</main></body></html>")
    return "".join(parts)


def main():
    plan, caught = check.checks()
    comp, copper = render.component_svg(plan), render.copper_svg(plan)
    (HERE / "perfboard-componentes.svg").write_text(comp)
    (HERE / "perfboard-cobre.svg").write_text(copper)
    (HERE / "guia.html").write_text(html(plan, caught, comp, copper))
    (HERE / "soldering-sheet.md").write_text(markdown(plan, caught))
    print("wrote guia.html, both SVG views and soldering-sheet.md")


if __name__ == "__main__":
    main()
