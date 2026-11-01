"""Write soldering-sheet.md from the validated layout (text until the drawn guide exists)."""

from board import name
import check

STAGES = {"power": "1. Alimentación y puentes de GND", "leds": "2. LED verde y amarillo",
          "panic": "3. Botón de pánico", "tx": "4. Emisor IR", "rx": "5. Receptor"}


def main():
    plan, caught = check.checks()
    out = ["# Hoja de soldadura (generada por `sheet.py`)", "",
           "F = fila 1–24 desde el borde con los números impresos; C = columna 1–32 impresa.",
           "Rieles: C7 GND, C14 3V3, C21 5V, C28 GND. Piezas por el lado impreso, soldadura",
           "por el lado de cobre. «Puente de cobre» = alambre desnudo o pata cortada entre",
           "dos pads vecinos del lado de cobre (no ocupa agujero).", ""]
    for stage, title in STAGES.items():
        out += [f"## {title}", "", "| Qué | Dónde |", "| --- | --- |"]
        for p in plan.parts:
            if p["stage"] == stage:
                pins = ", ".join(f"{pin} → {name(h)}" for pin, h in p["pins"].items())
                out.append(f"| {p['ref']} {p['value']} | {pins} |")
        for w in plan.wires:
            if w["stage"] == stage:
                out.append(f"| Cable aislado {w['net']} | {name(w['a'])} ↔ {name(w['b'])} |")
        for l in plan.links:
            if l["stage"] == stage:
                out.append(f"| Puente de cobre {l['net']} | {name(l['a'])} ↔ {name(l['b'])} |")
        for lead in plan.pi:
            if lead["stage"] == stage:
                out.append(f"| Cable de la Pi, pin físico {lead['physical']} ({lead['net']}) | {name(lead['hole'])} |")
        out.append("")
    out += ["## Mapa (lado de componentes)", "", "```", plan.ascii(), "```", "",
            f"Validado: todas las redes de `circuit-reference.json` unidas y sin cortos; "
            f"{len(caught)} errores típicos rechazados por `check.py`.", ""]
    (check.layout.board.HERE / "soldering-sheet.md").write_text("\n".join(out))


if __name__ == "__main__":
    main()
