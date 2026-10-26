# Python: nodes, gateway, and Faro control

Use this folder as the PyCharm project. All Raspberry Pi control code remains
Python; this scaffold does not introduce Arduino or C/C++ firmware.

## Create your environment

Both Pis already have the repository cloned. First update that existing
clone to the owner's reviewed/published revision using
[the Pi update procedure](../docs/optical-bringup.md#software-preparation-on-each-pi).
Run these commands from that clone's `python/` on macOS or GNU/Linux,
reusing this machine's `.venv` if present:

```bash
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m faronet info
```

Use `python -m pip` so packages go into the active interpreter. Run
`python -c "import sys; print(sys.executable)"` to check that it points to
`.venv/`. Run `deactivate` when you are done.
Inspect an existing broken or incompatible venv before changing it. Each
Pi creates/maintains its own environment; never copy venvs between machines.
On Pis install `requirements-gpio.txt` as described below. Worker tooling
and Rust/WASM compilation belong on the Mac, even though the full cloned
monorepo also contains `rust/` on each Pi.

In PyCharm, select `.venv/bin/python` as the project interpreter. A run
configuration can use module name `faronet`, parameters `info`, and this folder
as the working directory. `faronet info` also works after installation.

## Code map

- `src/faronet/cli.py`: terminal status and local simulation/authentication demos.
- `src/faronet/node/`: identities/signed directory, fragmentation, onion
  envelopes and a mesh simulation following proposal 0002; LAN transport
  and the interactive private chat remain pending.
- `src/faronet/gateway/`: offline HMAC/replay helpers; live bridge remains pending.
- `src/faronet/faro/`: libgpiod v2 GPIO backend, timestamped-edge acquisition,
  current breadboard pin profile, indicators and latched panic stop.
- `src/faronet/dispositivo_luz_adaptador/`: location for the required
  `DispositivoLuzAdaptador` library, frame/Manchester codec and simulated link.

The simulation commands have no GPIO side effects. Physical commands are
explicit (`gpio-monitor`, `optical-send`, `optical-listen`) and require
`--hardware-ready`; `gpio-preflight` reads metadata without requesting lines.
See [the optical bring-up guide](../docs/optical-bringup.md) for both Pis,
copyable commands, electrical checks, recovery and measurement limits.

The basic and RGB layouts in `hardware/breadboard/` share the same optical,
TX/RX indicator and panic pins. Basic is the default: no RGB GPIO is
inspected, claimed or driven. Add `--rgb` to preflight and the physical
command only when enabling the optional common-cathode debug LED on that
board. The peer can use either variant independently. RGB patterns are
provisional debugging output and do not control the link protocol.

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
The second board is now a Raspberry Pi 2 Model B running PiOS; its exact
Python and the PyNaCl/gpiod installation path there are unconfirmed, so keep
the code free of 3.12+-only syntax. See
[the Pi environment](../hardware/pi-environment.md); the suite passes on A,
while B's software tests are still pending. Create a fresh virtual environment on the Pi, rather than
copying the Mac environment. SSH metadata queries identify `/dev/gpiochip0`
as `pinctrl-bcm2835`, with 54 lines. The team accepted the official libgpiod v2
Python backend and BCM numbering; physical header positions must accompany
the current role assignments. A GPIO backend is the low-level implementation
that reads/writes pins. The current breadboard profile is implemented;
binding installation and metadata access have been verified on A's Pi,
while physical line I/O, analog operation and optical timing remain pending.

For the Pi, from `python/` with its virtual environment active:

```bash
python -m pip install -r requirements-gpio.txt
```

This installs the optional `gpio` extra, pinned to `gpiod==2.5.0` in
`pyproject.toml`. A Linux environment marker keeps the package out of macOS
installs. The default `requirements.txt` remains sufficient for laptop work.
The Python 3.14/ARM64 wheel was installed on A's Pi on October 25 and the
metadata API was exercised with `sudo`, without requesting lines.
[Official release](https://pypi.org/project/gpiod/2.5.0/)
Keep GPIO7-11 reserved for the existing SPI bus; GPIO0/1 are identification
pins, and lines 28-53 are outside the header. The exact role mapping follows
`hardware/breadboard/circuit-reference.json` and is checked by a test.

The current assembled circuits follow `hardware/breadboard/`; their basic
version includes TX/RX indication and physical panic, and the other version
adds optional RGB debugging. LCD and speaker/buzzer code are deferred until minimum requirements
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
