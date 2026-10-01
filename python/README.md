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

- `src/faronet/cli.py`: terminal entry point; currently reports scaffold status.
- `src/faronet/node/`: future mesh routing, directory, and private application.
- `src/faronet/gateway/`: future authenticated bridge to the Rust Worker.
- `src/faronet/faro/`: future GPIO, light transmission, indicators, and panic button.
- `src/faronet/dispositivo_luz_adaptador/`: location for the required
  `DispositivoLuzAdaptador` library.

The component packages currently contain only documentation. The CLI does not
open GPIO, communicate with peers, or send messages. No protocol interface is
fixed by this scaffold.

## Dependencies

`requirements.txt` installs this package in editable mode. The starter itself
uses only the standard library. `pyproject.toml` is the source of truth for
future runtime dependencies; pip installs its declared dependencies through
`-e .`. Add exact approved versions there when implementations need them.
Keep hardware-only packages in a separately documented optional dependency
group so laptop development stays usable.

The Raspberry Pi model/OS and GPIO backend are pending. The specification
requires a recognized cryptographic library but does not select one; PyNaCl is
a candidate. GPIO packages, PyNaCl, USB-serial libraries, WebSocket clients, and
Scapy are not installed speculatively. The gateway's HTTPS/WSS choice is also
pending.

## Local checks

```bash
python -m compileall -q src
python -m faronet --help
python -m faronet info
python -m pip check
```

These check the environment and starter entry point. They do not validate a
mesh protocol, circuit, anonymity, or cryptographic implementation.
