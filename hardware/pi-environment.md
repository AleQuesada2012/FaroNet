# Raspberry Pi reference environment

Recorded from the owner's command output on 2026-10-09. This describes the
inspected Pi; the second Pi's exact software versions have not been checked.
The boards' agreed model is Raspberry Pi 3 Model B rev 1.2.

| Detail | Reported value | Evidence |
| --- | --- | --- |
| Distribution | Ubuntu Server 26.04.1 LTS | Previously confirmed Server installation; `/etc/os-release` |
| Release/codename | 26.04, Resolute Raccoon (`resolute`) | `/etc/os-release` |
| Kernel architecture | `aarch64` (ARM64) | `uname -m` |
| User-space long integer width | 64 bits | `getconf LONG_BIT` |
| Kernel | `7.0.0-1020-raspi` | `uname -r` |
| System Python | 3.14.4 | `python3 --version` |

Python 3.14.4 meets the repository's declared Python >=3.11 requirement.
The first milestone was tested on the Mac using Python 3.14.7; its tests have
not yet been run on this Pi. Hardware bindings have not been installed or
tested.

## Reported GPIO device nodes

| Device | Owner/group | Mode | Reported SSH access probe |
| --- | --- | --- | --- |
| `/dev/gpiochip0` | `root:dialout` | `crw-rw----+` | Read `True`, write `True` |
| `/dev/gpiochip1` | `root:root` | `crw-------` | Read `False`, write `False` |
| `/dev/gpiochip2` | `root:root` | `crw-------` | Read `False`, write `False` |

The owner ran the read-only Python probe through SSH on 2026-10-09.
It reported effective filesystem read/write access to `gpiochip0`, despite
the login not being in `dialout`. The exact ACL grant has not been inspected;
there is no demonstrated need for a group or permission change on chip 0.
These access booleans alone did not prove a successful device open or ioctl.
The subsequent metadata commands below succeeded through the same SSH account.
Line requests, Python binding access and physical timing have not been tested.
Access in a future service context must be checked independently.

The probe also reported `No GPIO sysfs labels exposed`. It found no labels
through that interface; the reason has not been diagnosed. Character-device
metadata queries subsequently identified the controller successfully.

## Confirmed controller and header interpretation

The owner reported these successful queries through SSH on 2026-10-09:

```text
gpiodetect gpiochip0
gpiochip0 [pinctrl-bcm2835] (54 lines)
```

`gpioinfo -c gpiochip0` also returned all 54 lines. This confirms chip and
line metadata access, beyond a filesystem permission check. The controller
contains both header GPIOs and board-internal signals; 54 lines does not mean
54 usable header pins. GPIO numbers match line offsets on this inspected chip.

| Lines / BCM numbers | Reported information | Project treatment |
| --- | --- | --- |
| 0, 1 | `ID_SDA`, `ID_SCL` | Header positions 27/28; reserve for identification/advanced use |
| 2-27 | `GPIO2` through `GPIO27` | Header GPIOs; individual project roles still unassigned |
| 7, 8 | Outputs, active-low, consumers `spi0 CS1` and `spi0 CS0` | Already claimed by SPI; exclude from project roles |
| 9-11 | Inputs, no consumer shown | SPI0 data/clock pins; exclude while the current SPI bus remains enabled |
| 28-53 | Internal signals including Wi-Fi/SD/power functions; 47 is output `SMPS_SDA` | Outside the 40-pin GPIO header; exclude from project roles |

No consumer shown in `gpioinfo` is not a complete pin-multiplexer or peripheral
availability check. Before assigning a role, check the approved circuit and
any enabled peripheral using that pin. The SPI configuration remains unchanged.
The [official GPIO reference](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header)
and [Pi 3B revision 1.2 schematic](https://datasheets.raspberrypi.com/rpi3/raspberry-pi-3-b-reduced-schematics.pdf)
document the header and its alternate functions. Details and primary references
are also in [the compatibility research](../docs/research/gpio-ubuntu-26.04.md).

## Accepted backend and numbering

The owner accepted the official libgpiod v2 Python API (`gpiod`) and BCM
GPIO numbering on 2026-10-09. Use `/dev/gpiochip0` on the inspected Pi, with
the expected controller label `pinctrl-bcm2835`; re-identify it on the second
Pi rather than assume its device number. Physical header positions must be
documented alongside each approved BCM assignment. For example, BCM GPIO17
is line offset 17 on this chip and physical header position 11; this is an
explanation of numbering, not an assignment to a project role.

The repository pins `gpiod==2.5.0` in an optional Linux-only `gpio` extra.
The release provides a Python 3.14/ARM64 wheel and vendors libgpiod, so the
Python package and Ubuntu's inspection tools can have different versions.
[Official release](https://pypi.org/project/gpiod/2.5.0/)

After transferring the repository to the Pi, create its own virtual environment
using [the Python setup guide](../python/README.md). From `python/` with that
environment active, install the optional backend:

```bash
python -m pip install -r requirements-gpio.txt
```

This optional installation is documented, not performed on the Pi from this
session. The Python binding, line I/O and real optical timing still need
validation. The default laptop installation does not install `gpiod`.

Repository checks on 2026-10-09: all 41 Python tests passed; a macOS install
dry run of `requirements-gpio.txt` correctly excluded the Linux dependency;
pip resolved and downloaded the regular CPython 3.14/ARM64 glibc wheel from
PyPI. These packaging checks do not exercise the Pi's hardware or Python binding.

## Remaining hardware decisions

- Explicit BCM and physical header assignments for laser TX, conditioned RX,
  TX/RX indicators, RGB and panic; Python binding and line I/O validation.
- Exact emitter/receiver/comparator, signal conditioning, hysteresis and
  GPIO-compatible levels.
- Real optical timing, clock recovery, throughput/BER and behavior under the
  Node/Gateway workload; simulator durations are not hardware timing.
- Confirm the second Pi's environment during bring-up.

See [project decisions](../docs/decisions.md) and the
[hardware workspace](README.md). The first-milestone simulator requires no
GPIO package.
