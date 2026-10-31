"""BCM assignments from hardware/breadboard/circuit-reference.json (revision 7, no RGB)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pin:
    role: str
    bcm: int
    physical: int
    output: bool


PINS = (
    Pin("TX", 17, 11, True),
    Pin("OPT_RX", 27, 13, False),
    Pin("LED_TX", 22, 15, True),
    Pin("LED_RX", 23, 16, True),
    Pin("PANIC", 24, 18, False),
)
TX, RX, LED_TX, LED_RX, PANIC = (pin.bcm for pin in PINS)
CONTROLLER = "pinctrl-bcm2835"


def inspect_chip(path: str) -> dict:
    """Read chip/line metadata only; never request or reconfigure a line."""
    import gpiod

    with gpiod.Chip(path) as chip:
        info = chip.get_info()
        lines = []
        for pin in PINS:
            line = chip.get_line_info(pin.bcm)
            lines.append({
                "role": pin.role, "bcm": pin.bcm, "physical": pin.physical,
                "name": line.name, "used": line.used, "consumer": line.consumer,
            })
        return {
            "chip": path, "controller": info.label,
            "controller_matches": info.label == CONTROLLER,
            "lines": lines,
        }
