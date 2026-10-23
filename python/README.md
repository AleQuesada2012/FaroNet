# Python: nodes, gateway, and Faro control

Use this folder as the PyCharm project. All Raspberry Pi control code remains
Python; this scaffold does not introduce Arduino or C/C++ firmware.

## Create your environment

Run these commands from `python/` on macOS or GNU/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m faronet info
```

Use `python -m pip` so packages go into the active interpreter. Run
`python -c "import sys; print(sys.executable)"` to check that it points to
`.venv/`. Run `deactivate` when you are done.

In PyCharm, select `.venv/bin/python` as the project interpreter. A run
configuration can use module name `faronet`, parameters `info`, and this folder
as the working directory. `faronet info` also works after installation.

## Code map

- `src/faronet/cli.py`: terminal status and local simulation/authentication demos.
- `src/faronet/node/`: identities/signed directory, fragmentation, onion
  envelopes and a mesh simulation following proposal 0002; LAN transport
  and the interactive private chat remain pending.
- `src/faronet/gateway/`: offline HMAC/replay helpers; live bridge remains pending.
- `src/faronet/faro/`: future GPIO, light transmission, indicators, and panic button.
- `src/faronet/dispositivo_luz_adaptador/`: location for the required
  `DispositivoLuzAdaptador` library, frame/Manchester codec and simulated link.

The first milestone exchanges synthetic frames locally and tests offline
authentication. The CLI does not open GPIO or connect to real peers. The
Node and hardware Faro packages remain placeholders.

## Dependencies

`requirements.txt` installs this package in editable mode. The optical and
gateway modules use only the standard library; the node modules require
`pynacl==1.6.2`, declared in `pyproject.toml`. `pyproject.toml` is the source of truth for
future runtime dependencies; pip installs its declared dependencies through
`-e .`. Add exact approved versions there when implementations need them.
Keep hardware-only packages in a separately documented optional dependency
group so laptop development stays usable.

The inspected hardware target is Raspberry Pi 3 Model B rev 1.2 with Ubuntu
Server 26.04.1 LTS, ARM64, kernel `7.0.0-1020-raspi`, system Python 3.14.4.
The second board is now a Raspberry Pi 2 Model B v1.1, 32-bit only; its OS,
Python and the PyNaCl/gpiod installation path there are unconfirmed, so keep
the code free of 3.12+-only syntax. See
[the Pi environment](../hardware/pi-environment.md); tests on both boards
are still pending. Create a fresh virtual environment on the Pi, rather than
copying the Mac environment. SSH metadata queries identify `/dev/gpiochip0`
as `pinctrl-bcm2835`, with 54 lines. The team accepted the official libgpiod v2
Python backend and BCM numbering; physical header positions must accompany
the eventual role assignments. A GPIO backend is the low-level implementation
that reads/writes pins. Python binding/line I/O tests, exact pins and the laser
receiver circuit remain pending.

For the Pi, from `python/` with its virtual environment active:

```bash
python -m pip install -r requirements-gpio.txt
```

This installs the optional `gpio` extra, pinned to `gpiod==2.5.0` in
`pyproject.toml`. A Linux environment marker keeps the package out of macOS
installs. The default `requirements.txt` remains sufficient for laptop work.
The package release has a Python 3.14/ARM64 wheel; installation and use on
this Pi still need verification. [Official release](https://pypi.org/project/gpiod/2.5.0/)
Keep GPIO7-11 reserved for the existing SPI bus; GPIO0/1 are identification
pins, and lines 28-53 are outside the header. No project role is assigned yet.

The first iteration targets the laser link, with IR fallback, RGB debugging,
TX/RX indication, and the physical panic button alongside required software
features. LCD and speaker/buzzer code are deferred until minimum requirements
are met. The selected receiver approach uses a comparator with hysteresis and
digital GPIO input rather than an ADC. Its component pairing, conditioning,
logic levels, and measured timing remain unresolved.

The team selected PyNaCl for cryptography and HTTPS with HMAC-SHA-256 for
gateway requests. Proposal 0002 names the PyNaCl primitives now in use; key
lifecycle still needs its contract. The optical/HMAC foundation uses
Python's standard library.
Install runtime packages when their implementation slice needs them. The
approved GPIO package is optional; USB-serial, WebSocket-client and Scapy
dependencies have not been selected.
See [the decisions](../docs/decisions.md) and
[the first-milestone proposal](../docs/rfc/0001-first-milestone-proposal.md).

## Local checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q src
python -m faronet --help
python -m faronet info
python -m pip check
```

The tests validate the first-milestone frame, waveform and offline HMAC/replay
contract using shared synthetic fixtures. They do not establish a working
circuit, mesh protocol, deployed replay protection or anonymity.

## First-milestone demonstrations

With the virtual environment active, run:

```bash
python -m faronet simulate
python -m faronet simulate --scenario lost-ack
python -m faronet auth-demo
python -m faronet mesh-demo
```

The mesh demo sends one padded message from a Pi-3 Node to a laptop Node
through three relays, with the first hop over the simulated optical link,
then a reply; it prints anonymous counters only. The simulator exchanges Manchester-encoded frames between two synthetic
Faros, with scripted turns and a known virtual clock. It demonstrates loss,
corruption, duplicate suppression and bounded retries. The authentication
demo admits one synthetic request and rejects its replay using a fake store.
Both demonstrations run without hardware or network connections.

`dispositivo_luz_adaptador/frame.py` defines the accepted wire format;
`manchester.py` handles logical light levels; `simulation.py` provides the
simulated `DispositivoLuzAdaptador`, including `send_frame()` for externally
constructed frames. `gateway/auth.py` implements request signing/admission;
`gateway/testing.py` is an explicitly fake replay store. Shared examples live
in the root `fixtures/` folder. `node/identity.py`, `node/fragment.py`,
`node/envelope.py` and `node/mesh.py` implement proposal 0002. See
[the milestone guide](../docs/milestone-1.md) and
[the node slice guide](../docs/milestone-2.md) for boundaries and validation.
