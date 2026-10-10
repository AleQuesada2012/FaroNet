# GPIO on the reported Ubuntu 26.04 Raspberry Pi

Research checked on 2026-10-09. The owner has accepted the official gpiod v2 Python backend and BCM numbering. This note records the compatibility evidence; it is not a physical GPIO test.

## Reported environment

The user inspected **one** Raspberry Pi 3 Model B rev 1.2: Ubuntu Server 26.04.1 LTS (Resolute), `aarch64`/64-bit, kernel `7.0.0-1020-raspi`, Python `3.14.4`. These observations have not been independently checked on the device and do not establish the second Pi's environment.

Reported device permissions: `/dev/gpiochip0` is `0660`, owned by `root:dialout`, with a `+` ACL indicator; chips 1 and 2 are `0600`, owned by `root:root`. The inspected login is not in `dialout`. No login name, UID, or unrelated group memberships are retained here.

The user subsequently ran the permission probe over SSH: chip 0 reported `read=True`, `write=True`; chips 1 and 2 reported `False` for both. Neither documented `/sys/class/gpio` label pattern produced output. Those `os.access()` checks alone did not establish successful device opens or ioctls. The later successful `gpiodetect gpiochip0` and `gpioinfo -c gpiochip0` results below now establish reported chip/line metadata access. [Python access-check limitations](https://docs.python.org/3/library/os.html#os.access)

## Available software and accepted backend direction

Ubuntu's current Resolute package index lists the following; availability is distinct from installation on the Pi:

| Route | Verified published package | Relevant evidence |
| --- | --- | --- |
| Direct libgpiod Python API | `python3-libgpiod` **2.2.1-3build1**, arm64 | Package dependencies explicitly target Python `>=3.14~` and `<3.15`. [Ubuntu package](https://packages.ubuntu.com/fr/resolute/arm64/python/python3-libgpiod) |
| libgpiod inspection tools | `gpiod` **2.2.1-3build1**, arm64 | Includes the GPIO character-device tools. [Ubuntu package](https://packages.ubuntu.com/resolute/gpiod) |
| lgpio Python API | `python3-lgpio` **0.2.0.0-0ubuntu6**, arm64 | Package dependencies explicitly target Python `>=3.14~` and `<3.15`. [Ubuntu package](https://packages.ubuntu.com/fr/resolute/arm64/python/python3-lgpio) |
| GPIO Zero device API | `python3-gpiozero` **2.0.1-0ubuntu2**, architecture `all` | Recommends `python3-lgpio`; GPIO Zero calls a lower-level backend through a pin factory. [Ubuntu package](https://packages.ubuntu.com/resolute/python3-gpiozero), [pin factories](https://gpiozero.readthedocs.io/en/stable/api_pins.html) |

For a future isolated virtual environment, the official PyPI `gpiod` **2.5.0** release explicitly supports Python 3.14 and provides a regular CPython 3.14/aarch64/glibc wheel. It vendors libgpiod by default, independently of the system package. Its v2 API is incompatible with the old unofficial PyPI `gpiod` package. [Official release](https://pypi.org/project/gpiod/2.5.0/)

The published PyPI `lgpio` **0.2.2.0** wheel list stops at CPython 3.12; a source distribution exists, but a Python 3.14 build was not verified. GPIO Zero **2.0.1.post3** publishes a `py3-none-any` wheel and declares Python `>=3.9`; that metadata does not prove the full GPIO stack works on this board/kernel. [lgpio files](https://pypi.org/project/lgpio/), [GPIO Zero files](https://pypi.org/project/gpiozero/)

**Accepted direction:** the owner selected the **direct official gpiod/libgpiod v2 Python API** for FaroNet's eventual GPIO adapter. It has explicit Python 3.14/arm64 packaging evidence and exposes timestamped receive edges and event sequence numbers, which fit the planned optical decoder. That fit is an inference from the evidence; the Python binding has not yet been installed or tested on the Pi. [Python edge-event API](https://libgpiod.readthedocs.io/en/master/python_edge_event.html)

No packages were installed during this research. The owner can now run the inspection tools; no Python binding installation or runtime test on the Pi has been reported. An ordinary venv excludes system site packages by default, so an apt-installed Python module may not be visible inside it; keep the selected packaging route explicit in setup instructions. [Python venv documentation](https://docs.python.org/3/library/venv.html)

## Control access versus optical timing

Linux GPIO character-device API v2 was introduced in kernel 5.10; it provides chip information, line requests, values, and edge events. The reported 7.0 kernel is newer than that introduction. Metadata access has now succeeded; line requests, values, edge events, and physical behavior remain untested. Nanosecond timestamps are a representation and best estimate, not a nanosecond accuracy guarantee. [Kernel API](https://docs.kernel.org/userspace-api/gpio/chardev.html)

Ordinary output writes can control status LEDs and an eventual emitter driver. They do not provide a guaranteed Manchester waveform clock. lgpio describes its PWM/waves as software timed, and Python documents that `sleep()` may overrun because of scheduling. Physical transmission therefore needs separate measurement of pulse widths, missed receive events, load behavior, and complete-frame error rate before setting a bitrate. [lgpio upstream](https://github.com/joan2937/lg), [Python sleep](https://docs.python.org/3/library/time.html#time.sleep)

The identified controller is recorded below. No pin-role assignment, timing method, bitrate, or optical circuit has been selected by this note.

## Identify chips and interpret permissions

Do not identify the header controller by the numeral in `/dev/gpiochip0`. Inspect labels, line names, and consumers first. `gpiodetect` lists chip names, labels, and line counts; `gpioinfo` reads line configuration information. These metadata tools do not request output levels. [Official tools](https://libgpiod.readthedocs.io/en/master/gpio_tools.html), [chip-information ioctl](https://docs.kernel.org/userspace-api/gpio/gpio-get-chipinfo-ioctl.html)

Upstream Linux **v7.0** explicitly exposes read-only `label` and `ngpio` attributes at `/sys/class/gpio/chipX/`, when GPIO sysfs support is enabled. Its optional legacy interface exposes `/sys/class/gpio/gpiochipN/label`, where **N is the global GPIO base**, not the character-device chip number. The user's probe found neither label pattern on the Ubuntu-patched kernel; that does not negate the subsequently successful character-device metadata access. Do not assume `/sys/bus/gpio/devices/gpiochipN/label` exists universally. [v7.0 implementation, comments and registration](https://raw.githubusercontent.com/torvalds/linux/v7.0/drivers/gpio/gpiolib-sysfs.c)

The `+` means additional access-control information is present. A named-user ACL can grant access even without membership in the owning group, subject to its ACL mask. The reported probe confirms read/write access checks succeed for chip 0 despite the missing `dialout` membership; its exact ACL entries remain uninspected. These facts provide no reason to change group membership or permissions for the next metadata inspection. [GNU ls](https://www.gnu.org/software/coreutils/manual/html_node/What-information-is-listed.html), [Ubuntu ACL access algorithm](https://manpages.ubuntu.com/manpages/resolute/man5/acl.5.html)

## Reported controller and header interpretation

The owner successfully ran the scoped inspection commands:

```sh
gpiodetect gpiochip0
gpioinfo -c gpiochip0
```

The reported controller is **`pinctrl-bcm2835`, 54 lines**. Line offsets 0/1 are named `ID_SDA`/`ID_SCL`; offsets 2–27 are named `GPIO2`–`GPIO27`. GPIO7 and GPIO8 are active-low outputs with consumers `spi0 CS1` and `spi0 CS0`; offsets 28–53 describe board functions, including line 47 `SMPS_SDA` as an output. These are owner-reported metadata results, not independently obtained measurements. The commands open the chip and inspect chip/line information without claiming lines; line information does not include actual input values. [Resolute gpiodetect manual](https://manpages.ubuntu.com/manpages/resolute/man1/gpiodetect.1.html), [Resolute gpioinfo manual](https://manpages.ubuntu.com/manpages/resolute/man1/gpioinfo.1.html), [kernel line-information API](https://docs.kernel.org/userspace-api/gpio/gpio-v2-get-lineinfo-ioctl.html)

The Pi 3 Model B's J8 header exposes GPIO0–27, alongside power and ground; the controller's other lines are not extra J8 GPIOs. BCM identifiers differ from physical header positions. Selected reference mappings are below; these are **not FaroNet pin assignments**. [Official Pi 3B schematic](https://datasheets.raspberrypi.com/rpi3/raspberry-pi-3-b-reduced-schematics.pdf), [official header documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header)

| BCM GPIO | Physical J8 pin | Relevant function |
| --- | --- | --- |
| 0 | 27 | ID_SD / HAT identification SDA |
| 1 | 28 | ID_SC / HAT identification SCL |
| 7 | 26 | SPI0 CE1 |
| 8 | 24 | SPI0 CE0 |
| 9 | 21 | SPI0 MISO |
| 10 | 19 | SPI0 MOSI |
| 11 | 23 | SPI0 SCLK |
| 17 | 11 | GPIO; numbering example only |

GPIO0/1 remain reserved for board identification even with HATs removed. Preserve the existing SPI configuration: GPIO7/8 are already claimed, and GPIO9–11 are the associated SPI0 data/clock pins and should also be excluded from general FaroNet allocation while SPI remains enabled. [Official HAT design requirements](https://github.com/raspberrypi/hats/blob/master/designguide.md#gpio-requirements), [official SPI0 mapping](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#pin-gpio-mappings)

A blank consumer and `input` are a snapshot of GPIO metadata, not a guarantee that a pin is free of alternate-function muxing, boot reservations, external connections, or later contention. Consumer labels may also be empty when a user does not supply one; pinctrl and GPIO are distinct cooperating subsystems. [Kernel consumer semantics](https://docs.kernel.org/userspace-api/gpio/chardev.html), [kernel pin-control/GPIO interaction](https://docs.kernel.org/driver-api/pin-control.html#drivers-needing-both-pin-control-and-gpios)

**Discovery conclusion:** this Pi's environment and controller metadata support the owner's accepted **official gpiod/libgpiod v2 Python backend** and **BCM GPIO notation**, with physical J8 positions recorded separately for wiring. The eventual adapter must resolve the controller by its validated identity and mapping rather than assume the numeric chip name is stable. Exact FaroNet pin assignments remain pending. The Python binding has not yet been installed or tested on the Pi; GPIO line I/O, optical timing, the circuit, and the second Pi remain unvalidated. No further diagnostics are requested by this note.
