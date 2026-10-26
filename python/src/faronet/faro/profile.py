"""BCM assignments from hardware/breadboard/circuit-reference.json (revision 6)."""

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
    Pin("RGB_R", 5, 29, True),
    Pin("RGB_G", 6, 31, True),
    Pin("RGB_B", 13, 33, True),
)
TX, RX, LED_TX, LED_RX, PANIC, RED, GREEN, BLUE = (pin.bcm for pin in PINS)
BASIC_PINS = PINS[:5]
RGB_PINS = PINS[5:]
CONTROLLER = "pinctrl-bcm2835"


def pins_for(rgb: bool = False) -> tuple[Pin, ...]:
    """Basic is the default; RGB adds only the optional debug outputs."""
    return BASIC_PINS + RGB_PINS if rgb else BASIC_PINS


def inspect_chip(path: str, rgb: bool = False) -> dict:
    """Read chip/line metadata only; never request or reconfigure a line."""
    import gpiod

    with gpiod.Chip(path) as chip:
        info = chip.get_info()
        lines = []
        for pin in pins_for(rgb):
            line = chip.get_line_info(pin.bcm)
            lines.append({
                "role": pin.role, "bcm": pin.bcm, "physical": pin.physical,
                "name": line.name, "used": line.used, "consumer": line.consumer,
            })
        return {
            "variant": "rgb" if rgb else "basic",
            "chip": path, "controller": info.label,
            "controller_matches": info.label == CONTROLLER,
            "lines": lines,
        }
